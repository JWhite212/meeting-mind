"""
MeetingMind — main entry point and orchestrator.

Wires together the detector, audio capture, transcriber, summariser,
and output writers into a cohesive pipeline. Can run as:

  1. A daemon that auto-detects meetings:
       python -m src.main

  2. A one-shot recorder (skip detection, record immediately):
       python -m src.main --record-now

  3. Process an existing audio file (skip detection and capture):
       python -m src.main --process /path/to/audio.wav

The daemon mode is intended to be run via launchd on macOS so it
starts automatically on login and runs in the background.
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from dataclasses import asdict
from pathlib import Path

from src.audio_capture import AudioCapture
from src.detector import MeetingEvent, MeetingState, TeamsDetector
from src.diariser import Diariser
from src.output.markdown_writer import MarkdownWriter
from src.output.notion_writer import NotionWriter
from src.summariser import Summariser
from src.transcriber import Transcriber
from src.utils.config import load_config

logger = logging.getLogger("meetingmind")


class MeetingMind:
    """
    Top-level orchestrator. Connects the detector's callbacks to
    the recording pipeline and manages the lifecycle of each
    meeting session.
    """

    def __init__(self, config_path: Path | None = None):
        self._config = load_config(config_path)
        self._setup_logging()

        self._detector = TeamsDetector(self._config.detection)
        self._capture = AudioCapture(self._config.audio)
        self._transcriber = Transcriber(self._config.transcription)
        self._summariser = Summariser(self._config.summarisation)
        self._diariser = (
            Diariser(self._config.diarisation)
            if self._config.diarisation.enabled
            else None
        )

        # If diarisation is enabled, keep source files for comparison.
        if self._diariser:
            self._config.audio.keep_source_files = True

        # Output writers (initialised based on config).
        self._md_writer = (
            MarkdownWriter(self._config.markdown)
            if self._config.markdown.enabled
            else None
        )
        self._notion_writer = (
            NotionWriter(self._config.notion)
            if self._config.notion.enabled
            else None
        )

        self._meeting_started_at: float = 0.0
        self._active_meeting_id: str | None = None

        # API server and event system (initialised lazily in run_daemon).
        self._api_server = None
        self._event_bus = None

        # Wire up detector callbacks.
        self._detector.on_meeting_start = self._on_meeting_start
        self._detector.on_meeting_end = self._on_meeting_end

    def _setup_logging(self) -> None:
        """Configure logging to both console and file."""
        log_level = getattr(logging, self._config.logging.level.upper(), logging.INFO)
        log_file = self._config.logging.log_file

        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_file, encoding="utf-8"),
            ],
        )

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, **kwargs) -> None:
        """Emit an event if the EventBus is active."""
        if self._event_bus:
            self._event_bus.emit({"type": event_type, **kwargs})

    def _get_daemon_state(self) -> str:
        """Return current daemon state for the API."""
        if self._capture.is_recording:
            return "recording"
        state = self._detector.state
        if state == MeetingState.ACTIVE:
            return "recording"
        return "idle"

    def _get_active_meeting(self) -> dict | None:
        """Return info about the active meeting, or None."""
        if not self._capture.is_recording:
            return None
        return {
            "meeting_id": self._active_meeting_id,
            "started_at": self._meeting_started_at,
            "elapsed_seconds": time.time() - self._meeting_started_at,
        }

    # ------------------------------------------------------------------
    # Detector callbacks
    # ------------------------------------------------------------------

    def _on_meeting_start(self, event: MeetingEvent) -> None:
        """Called by the detector when a Teams meeting begins."""
        self._meeting_started_at = event.started_at or time.time()
        logger.info("Starting audio capture...")

        self._emit("meeting.started", started_at=self._meeting_started_at)

        try:
            self._capture.start()
        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}", exc_info=True)
            self._emit("pipeline.error", stage="capture", error=str(e))

    def _on_meeting_end(self, event: MeetingEvent) -> None:
        """Called by the detector when a Teams meeting ends."""
        logger.info("Stopping audio capture and processing...")
        self._emit(
            "meeting.ended",
            duration=event.duration_seconds,
        )
        audio_path = self._capture.stop()

        if audio_path is None or not audio_path.exists():
            logger.error("No audio file produced. Skipping processing.")
            return

        self._process_audio(
            audio_path=audio_path,
            started_at=event.started_at,
            duration_seconds=event.duration_seconds,
        )

    # ------------------------------------------------------------------
    # Processing pipeline
    # ------------------------------------------------------------------

    def _process_audio(
        self,
        audio_path: Path,
        started_at: float = 0.0,
        duration_seconds: float = 0.0,
    ) -> None:
        """
        Run the full pipeline on a captured audio file:
        transcribe -> summarise -> write outputs.

        If the API server is running, persists the meeting to the
        database and emits events for real-time UI updates.
        """
        if started_at == 0.0:
            started_at = time.time()

        meeting_id = self._active_meeting_id

        # Persist audio to a durable location if the API server is running.
        persistent_audio_path = audio_path
        if self._api_server and self._api_server.repo:
            import shutil
            audio_dir = Path(os.path.expanduser("~/.local/share/meetingmind/audio"))
            audio_dir.mkdir(parents=True, exist_ok=True)
            persistent_audio_path = audio_dir / audio_path.name
            if audio_path != persistent_audio_path:
                shutil.copy2(audio_path, persistent_audio_path)

        # Create meeting record in DB.
        if self._api_server and self._api_server.repo and self._api_server.loop:
            import asyncio
            loop = self._api_server.loop
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._api_server.repo.create_meeting(started_at=started_at, status="transcribing"),
                    loop,
                )
                meeting_id = future.result(timeout=5)
                self._active_meeting_id = meeting_id
                # Update with audio path.
                asyncio.run_coroutine_threadsafe(
                    self._api_server.repo.update_meeting(
                        meeting_id,
                        audio_path=str(persistent_audio_path),
                    ),
                    loop,
                )
            except Exception as e:
                logger.warning(f"Failed to create meeting record: {e}")

        # Step 1: Transcribe.
        logger.info("Transcribing audio...")
        self._emit("pipeline.stage", meeting_id=meeting_id, stage="transcribing")

        def on_segment(seg):
            self._emit(
                "transcript.segment",
                meeting_id=meeting_id,
                segment=asdict(seg),
            )

        try:
            transcript = self._transcriber.transcribe(
                audio_path, on_segment=on_segment
            )
        except Exception as e:
            logger.error(f"Transcription failed: {e}", exc_info=True)
            self._emit("pipeline.error", meeting_id=meeting_id, stage="transcribing", error=str(e))
            self._db_update(meeting_id, status="error")
            return

        if transcript.word_count < 5:
            logger.warning(
                f"Transcript too short ({transcript.word_count} words). "
                f"Skipping summarisation."
            )
            self._db_update(meeting_id, status="error")
            return

        if duration_seconds == 0.0:
            duration_seconds = transcript.duration_seconds

        # Step 2: Diarise (if enabled and source files are available).
        if self._diariser:
            sys_path = self._capture.system_audio_path
            mic_path = self._capture.mic_audio_path
            if sys_path and mic_path:
                logger.info("Running speaker diarisation...")
                self._emit("pipeline.stage", meeting_id=meeting_id, stage="diarising")
                try:
                    transcript = self._diariser.diarise(
                        transcript, sys_path, mic_path
                    )
                except Exception as e:
                    logger.error(f"Diarisation failed: {e}", exc_info=True)

        # Step 3: Summarise.
        logger.info("Generating summary...")
        self._emit("pipeline.stage", meeting_id=meeting_id, stage="summarising")
        try:
            summary = self._summariser.summarise(transcript)
        except Exception as e:
            logger.error(f"Summarisation failed: {e}", exc_info=True)
            self._emit("pipeline.error", meeting_id=meeting_id, stage="summarising", error=str(e))
            self._db_update(meeting_id, status="error")
            return

        # Persist transcript and summary to DB.
        self._db_update(
            meeting_id,
            title=summary.title or "Untitled Meeting",
            ended_at=started_at + duration_seconds,
            duration_seconds=duration_seconds,
            status="complete",
            transcript_json=json.dumps(transcript.to_dict()),
            summary_markdown=summary.raw_markdown,
            tags=summary.tags,
            language=transcript.language,
            word_count=transcript.word_count,
        )

        # Step 4: Write outputs.
        self._emit("pipeline.stage", meeting_id=meeting_id, stage="writing")

        if self._md_writer:
            try:
                md_path = self._md_writer.write(
                    summary, transcript, started_at, duration_seconds
                )
                logger.info(f"Markdown output: {md_path}")
            except Exception as e:
                logger.error(f"Markdown write failed: {e}", exc_info=True)

        if self._notion_writer:
            try:
                page_url = self._notion_writer.write(
                    summary, transcript, started_at, duration_seconds
                )
                logger.info(f"Notion output: {page_url}")
            except Exception as e:
                logger.error(f"Notion write failed: {e}", exc_info=True)

        self._emit("pipeline.complete", meeting_id=meeting_id)
        self._active_meeting_id = None
        logger.info("Processing complete.")

    def _db_update(self, meeting_id: str | None, **fields) -> None:
        """Helper to update a meeting record in the database (fire-and-forget)."""
        if not meeting_id or not self._api_server or not self._api_server.repo:
            return
        loop = self._api_server.loop
        if not loop or loop.is_closed():
            return
        import asyncio
        try:
            asyncio.run_coroutine_threadsafe(
                self._api_server.repo.update_meeting(meeting_id, **fields),
                loop,
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Manual recording (called from API)
    # ------------------------------------------------------------------

    def api_start_recording(self) -> None:
        """Start a manual recording session via the API."""
        self._meeting_started_at = time.time()
        self._emit("meeting.started", started_at=self._meeting_started_at)
        self._capture.start()

    def api_stop_recording(self) -> None:
        """Stop a manual recording and trigger processing. Runs synchronously."""
        started_at = self._meeting_started_at
        self._emit("meeting.ended", duration=time.time() - started_at)
        audio_path = self._capture.stop()

        if audio_path and audio_path.exists():
            duration = time.time() - started_at
            self._process_audio(audio_path, started_at, duration)

    # ------------------------------------------------------------------
    # Run modes
    # ------------------------------------------------------------------

    def _start_api_server(self) -> None:
        """Start the API server on a background thread if enabled."""
        if not self._config.api.enabled:
            return

        from src.api.events import EventBus
        from src.api.server import ApiServer

        self._event_bus = EventBus()
        self._api_server = ApiServer(
            host=self._config.api.host,
            port=self._config.api.port,
            event_bus=self._event_bus,
        )
        self._api_server.set_state_accessors(
            self._get_daemon_state,
            self._get_active_meeting,
        )
        self._api_server.set_recording_controls(
            start=self.api_start_recording,
            stop=self.api_stop_recording,
            is_recording=lambda: self._capture.is_recording,
        )
        self._api_server.start()

        # Give the server a moment to bind.
        time.sleep(0.5)

    def run_daemon(self) -> None:
        """
        Run as a background daemon, polling for Teams meetings.
        Blocks until interrupted with SIGINT/SIGTERM.
        """
        logger.info("MeetingMind daemon starting...")

        # Start the API server for UI communication.
        self._start_api_server()

        # Handle graceful shutdown.
        def shutdown_handler(signum, frame):
            logger.info("Shutdown signal received.")
            self._detector.stop()
            if self._capture.is_recording:
                logger.info("Stopping active recording...")
                audio_path = self._capture.stop()
                if audio_path and audio_path.exists():
                    duration = time.time() - self._meeting_started_at
                    self._process_audio(
                        audio_path, self._meeting_started_at, duration
                    )
            if self._api_server:
                self._api_server.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

        # Blocking poll loop.
        self._detector.run()

    def run_record_now(self) -> None:
        """
        Skip detection and start recording immediately.
        Press Ctrl+C to stop recording and trigger processing.
        """
        logger.info("Manual recording mode. Press Ctrl+C to stop.")
        self._start_api_server()
        started_at = time.time()

        self._capture.start()

        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass

        audio_path = self._capture.stop()
        duration = time.time() - started_at

        if audio_path and audio_path.exists():
            self._process_audio(audio_path, started_at, duration)
        else:
            logger.error("No audio captured.")

    def run_process_file(self, audio_path: str) -> None:
        """
        Skip detection and capture; process an existing audio file
        directly through the transcribe -> summarise -> output pipeline.
        """
        path = Path(audio_path)
        if not path.exists():
            logger.error(f"File not found: {path}")
            sys.exit(1)

        self._start_api_server()
        logger.info(f"Processing existing file: {path}")
        self._process_audio(path)


def main():
    parser = argparse.ArgumentParser(
        description="MeetingMind: auto-detect, transcribe, and summarise Teams meetings.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config.yaml (default: ./config.yaml)",
    )
    parser.add_argument(
        "--record-now",
        action="store_true",
        help="Skip meeting detection. Start recording immediately.",
    )
    parser.add_argument(
        "--process",
        type=str,
        default=None,
        help="Skip detection and capture. Process an existing audio file.",
    )

    args = parser.parse_args()
    config_path = Path(args.config) if args.config else None

    app = MeetingMind(config_path)

    if args.process:
        app.run_process_file(args.process)
    elif args.record_now:
        app.run_record_now()
    else:
        app.run_daemon()


if __name__ == "__main__":
    main()
