"""
Audio device listing endpoint.

GET /api/devices — returns available audio input devices.
"""

import logging

import sounddevice as sd
from fastapi import APIRouter

from src.api.schemas import DeviceListResponse

logger = logging.getLogger("contextrecall.api.devices")

router = APIRouter()


def _resolve_default_input_index() -> int | None:
    """Return the system default input device index, or None if unset.

    sd.default.device is a (input, output) tuple but can return -1 (no
    default), None, or raise on some configurations. Treat all of those
    as "no default" rather than crashing the endpoint (Bug A6).
    """
    try:
        default_input = sd.default.device[0]
    except Exception:
        return None
    if default_input is None or default_input < 0:
        return None
    return default_input


@router.get("/api/devices", response_model=DeviceListResponse, summary="List audio devices")
async def list_devices():
    try:
        devices = sd.query_devices()
    except Exception:
        logger.warning("sd.query_devices failed; returning empty list", exc_info=True)
        return {"devices": []}

    default_idx = _resolve_default_input_index()

    inputs = []
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            inputs.append(
                {
                    "index": i,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "sample_rate": dev["default_samplerate"],
                    "is_default": default_idx is not None and i == default_idx,
                }
            )
    return {"devices": inputs}
