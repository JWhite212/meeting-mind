"""Integration test: full pipeline from detection to output."""

import time
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.detector import MeetingEvent, MeetingState
from src.main import MeetingMind
from src.summariser import MeetingSummary
from src.transcriber import Transcript, TranscriptSegment

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_config(tmp_path):
    """Create a minimal config.yaml for MeetingMind init."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    config = {
        "detection": {"poll_interval_seconds": 1},
        "audio": {
            "sample_rate": 16000,
            "temp_audio_dir": str(tmp_path / "audio"),
        },
        "transcription": {"model_size": "tiny.en"},
        "summarisation": {"backend": "ollama"},
        "markdown": {"enabled": False},
        "notion": {"enabled": False},
        "diarisation": {"enabled": False},
        "api": {"enabled": False},
        "logging": {
            "level": "WARNING",
            "log_file": str(log_dir / "test.log"),
        },
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(config))
    return path


@pytest.fixture
def audio_file(tmp_path):
    """Create a minimal fake WAV file."""
    path = tmp_path / "test_recording.wav"
    path.write_bytes(b"RIFF" + b"\x00" * 40)
    return path


def _make_transcript(word_count_target=20):
    words = " ".join(f"word{i}" for i in range(word_count_target))
    return Transcript(
        segments=[TranscriptSegment(start=0.0, end=60.0, text=words)],
        language="en",
        language_probability=0.99,
        duration_seconds=60.0,
    )


def _make_summary():
    return MeetingSummary(
        raw_markdown="# Integration Test\n\n## Summary\nPipeline ran end-to-end.",
        title="Integration Test Meeting",
        tags=["integration", "test"],
    )


def _make_start_event():
    return MeetingEvent(
        state=MeetingState.ACTIVE,
        started_at=time.time(),
    )


def _make_end_event(started_at):
    now = time.time()
    return MeetingEvent(
        state=MeetingState.IDLE,
        started_at=started_at,
        ended_at=now,
        duration_seconds=now - started_at,
    )


# ---------------------------------------------------------------------------
# Test 1: detector callbacks drive capture and pipeline
# ---------------------------------------------------------------------------


@patch("src.main.Summariser")
@patch("src.main.TeamsDetector")
@patch("src.main.Transcriber")
@patch("src.main.AudioCapture")
def test_full_pipeline_detection_to_output(
    mock_capture_cls,
    mock_transcriber_cls,
    mock_detector_cls,
    mock_summariser_cls,
    tmp_config,
    audio_file,
):
    """_on_meeting_start starts capture; _on_meeting_end stops it and runs pipeline."""
    app = MeetingMind(config_path=tmp_config)

    # Configure transcriber and summariser mocks.
    app._transcriber.transcribe.return_value = _make_transcript()
    app._summariser.summarise.return_value = _make_summary()

    # Configure capture mock: stop() returns the audio file path.
    app._capture.start.return_value = None
    app._capture.stop.return_value = audio_file
    app._capture.is_recording = False

    # Attach a simple event bus spy so we can verify events are emitted.
    emitted_events = []
    mock_bus = MagicMock()
    mock_bus.emit.side_effect = lambda ev: emitted_events.append(ev)
    app._event_bus = mock_bus

    # Trigger meeting start.
    start_event = _make_start_event()
    app._on_meeting_start(start_event)

    # Capture should have been started.
    app._capture.start.assert_called_once()

    # meeting.started event should have been emitted.
    started_types = [e["type"] for e in emitted_events]
    assert "meeting.started" in started_types

    # Trigger meeting end.
    end_event = _make_end_event(start_event.started_at)
    app._on_meeting_end(end_event)

    # Capture stop was called.
    app._capture.stop.assert_called_once()

    # meeting.ended event should have been emitted.
    ended_types = [e["type"] for e in emitted_events]
    assert "meeting.ended" in ended_types

    # Wait for the background processing thread to finish.
    for future in app._processing_futures:
        future.result(timeout=30)

    # Transcription and summarisation ran.
    app._transcriber.transcribe.assert_called_once()
    app._summariser.summarise.assert_called_once()

    # pipeline.complete event should have been emitted.
    all_types = [e["type"] for e in emitted_events]
    assert "pipeline.complete" in all_types


@patch("src.main.Summariser")
@patch("src.main.TeamsDetector")
@patch("src.main.Transcriber")
@patch("src.main.AudioCapture")
def test_pipeline_stage_events_emitted(
    mock_capture_cls,
    mock_transcriber_cls,
    mock_detector_cls,
    mock_summariser_cls,
    tmp_config,
    audio_file,
):
    """pipeline.stage events are emitted for transcribing, summarising, and writing."""
    app = MeetingMind(config_path=tmp_config)
    app._transcriber.transcribe.return_value = _make_transcript()
    app._summariser.summarise.return_value = _make_summary()

    emitted_events = []
    mock_bus = MagicMock()
    mock_bus.emit.side_effect = lambda ev: emitted_events.append(ev)
    app._event_bus = mock_bus

    # Run the pipeline directly (same approach as test_orchestrator.py).
    app._process_audio(audio_file, started_at=time.time(), duration_seconds=60.0)

    stage_events = [e for e in emitted_events if e.get("type") == "pipeline.stage"]
    stages = [e["stage"] for e in stage_events]
    assert "transcribing" in stages
    assert "summarising" in stages
    assert "writing" in stages


# ---------------------------------------------------------------------------
# Test 2: manual recording API flow (api_start_recording / api_stop_recording)
# ---------------------------------------------------------------------------


@patch("src.main.Summariser")
@patch("src.main.TeamsDetector")
@patch("src.main.Transcriber")
@patch("src.main.AudioCapture")
def test_manual_recording_api_flow(
    mock_capture_cls,
    mock_transcriber_cls,
    mock_detector_cls,
    mock_summariser_cls,
    tmp_config,
    audio_file,
):
    """api_start_recording() starts capture; api_stop_recording() triggers pipeline."""
    app = MeetingMind(config_path=tmp_config)

    app._transcriber.transcribe.return_value = _make_transcript()
    app._summariser.summarise.return_value = _make_summary()

    # stop() must return a real path so _process_audio is submitted.
    app._capture.stop.return_value = audio_file
    app._capture.is_recording = False
    app._capture.mic_available = True

    emitted_events = []
    mock_bus = MagicMock()
    mock_bus.emit.side_effect = lambda ev: emitted_events.append(ev)
    app._event_bus = mock_bus

    # Start manual recording.
    app.api_start_recording()
    app._capture.start.assert_called_once()

    emitted_types = [e["type"] for e in emitted_events]
    assert "meeting.started" in emitted_types

    # Stop recording and allow pipeline to run via the executor.
    app.api_stop_recording()

    # Wait for background processing to complete.
    app._processing_executor.shutdown(wait=True)

    # Pipeline ran.
    app._transcriber.transcribe.assert_called_once()
    app._summariser.summarise.assert_called_once()

    all_types = [e["type"] for e in emitted_events]
    assert "meeting.ended" in all_types
    assert "pipeline.complete" in all_types


@patch("src.main.Summariser")
@patch("src.main.TeamsDetector")
@patch("src.main.Transcriber")
@patch("src.main.AudioCapture")
def test_capture_start_failure_does_not_run_pipeline(
    mock_capture_cls,
    mock_transcriber_cls,
    mock_detector_cls,
    mock_summariser_cls,
    tmp_config,
):
    """If audio capture fails to start, _on_meeting_start emits error and pipeline is skipped."""
    app = MeetingMind(config_path=tmp_config)
    app._capture.start.side_effect = RuntimeError("No audio device")

    emitted_events = []
    mock_bus = MagicMock()
    mock_bus.emit.side_effect = lambda ev: emitted_events.append(ev)
    app._event_bus = mock_bus

    # Should not raise.
    app._on_meeting_start(_make_start_event())

    app._capture.start.assert_called_once()

    # A pipeline.error event should have been emitted.
    error_events = [e for e in emitted_events if e.get("type") == "pipeline.error"]
    assert error_events, "Expected a pipeline.error event on capture failure"
    assert error_events[0]["stage"] == "capture"

    # No meeting.started event (capture failed before state was updated).
    started_types = [e["type"] for e in emitted_events]
    assert "meeting.started" not in started_types

    # Transcriber and summariser should never have been called.
    app._transcriber.transcribe.assert_not_called()
    app._summariser.summarise.assert_not_called()
