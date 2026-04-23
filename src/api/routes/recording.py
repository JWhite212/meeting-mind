"""
Manual recording control endpoints.

POST /api/record/start — begin recording immediately (skips detection).
POST /api/record/stop  — stop the active recording and trigger processing.
"""

import logging
import threading
import time

from fastapi import APIRouter, HTTPException

from src.api.schemas import RecordStartResponse, RecordStopResponse
from src.audio_capture import AudioCaptureError

logger = logging.getLogger("meetingmind.api.recording")

router = APIRouter()

_start_recording = None
_stop_recording = None
_stop_recording_deferred = None
_is_recording = None
_is_stopping = None


def init(start_recording, stop_recording, stop_deferred, is_recording, is_stopping=None) -> None:
    """Inject recording control callbacks from the orchestrator."""
    global _start_recording, _stop_recording, _stop_recording_deferred, _is_recording, _is_stopping
    _start_recording = start_recording
    _stop_recording = stop_recording
    _stop_recording_deferred = stop_deferred
    _is_recording = is_recording
    _is_stopping = is_stopping


@router.post("/api/record/start", response_model=RecordStartResponse, summary="Start recording")
async def start_recording():
    if not _start_recording or not _is_recording:
        raise HTTPException(status_code=503, detail="Recording controls not available")

    if _is_recording():
        raise HTTPException(status_code=409, detail="Already recording")

    if _is_stopping and _is_stopping():
        raise HTTPException(status_code=409, detail="Recording is still stopping")

    try:
        _start_recording()
    except (AudioCaptureError, OSError) as e:
        logger.error("Failed to start recording: %s", e)
        raise HTTPException(status_code=500, detail="Failed to start recording. Check daemon logs.")

    return {"status": "recording", "started_at": time.time()}


@router.post("/api/record/stop", response_model=RecordStopResponse, summary="Stop recording")
async def stop_recording(defer: bool = False):
    if not _stop_recording or not _is_recording:
        raise HTTPException(status_code=503, detail="Recording controls not available")

    if not _is_recording():
        raise HTTPException(status_code=409, detail="Not recording")

    if defer:
        if not _stop_recording_deferred:
            raise HTTPException(status_code=503, detail="Deferred stop not available")
    if defer and _stop_recording_deferred:
        # Stop recording and save audio without processing.
        try:
            meeting_id = _stop_recording_deferred()
        except (AudioCaptureError, OSError) as e:
            logger.error("Failed to defer recording: %s", e)
            raise HTTPException(
                status_code=500,
                detail="Failed to stop recording. Check daemon logs.",
            )
        return {"status": "deferred", "meeting_id": meeting_id}

    # Run stop + processing on a background thread so we don't block
    # the event loop (stop() blocks while merging audio files).
    thread = threading.Thread(
        target=_stop_recording,
        name="manual-stop",
        daemon=True,
    )
    thread.start()

    return {"status": "stopping"}
