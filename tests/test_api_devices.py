"""Tests for src/api/routes/devices.py — audio device listing."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import src.api.auth as auth_mod
from src.api.auth import verify_token
from src.api.routes import devices as devices_routes

TEST_TOKEN = "test-token-for-devices-tests"


def _make_app() -> FastAPI:
    app = FastAPI()
    auth_deps = [Depends(verify_token)]
    app.include_router(devices_routes.router, dependencies=auth_deps)
    return app


def _auth_headers():
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture(autouse=True)
def _patch_auth():
    original = auth_mod._auth_token
    auth_mod._auth_token = TEST_TOKEN
    yield
    auth_mod._auth_token = original


def test_list_devices_returns_inputs_only():
    mock_devices = [
        {
            "name": "Built-in Mic",
            "max_input_channels": 2,
            "max_output_channels": 0,
            "default_samplerate": 44100.0,
        },
        {
            "name": "Speakers",
            "max_input_channels": 0,
            "max_output_channels": 2,
            "default_samplerate": 44100.0,
        },
        {
            "name": "BlackHole 2ch",
            "max_input_channels": 2,
            "max_output_channels": 2,
            "default_samplerate": 48000.0,
        },
    ]
    mock_default = MagicMock()
    mock_default.device = [0, 1]

    app = _make_app()
    with TestClient(app) as c:
        with patch("src.api.routes.devices.sd.query_devices", return_value=mock_devices):
            with patch("src.api.routes.devices.sd.default", mock_default):
                resp = c.get("/api/devices", headers=_auth_headers())
                assert resp.status_code == 200
                data = resp.json()
                # Only devices with max_input_channels > 0.
                assert len(data["devices"]) == 2
                names = [d["name"] for d in data["devices"]]
                assert "Built-in Mic" in names
                assert "BlackHole 2ch" in names
                assert "Speakers" not in names


def test_list_devices_marks_default():
    mock_devices = [
        {
            "name": "USB Mic",
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 48000.0,
        },
        {
            "name": "Built-in Mic",
            "max_input_channels": 2,
            "max_output_channels": 0,
            "default_samplerate": 44100.0,
        },
    ]
    mock_default = MagicMock()
    mock_default.device = [1, 0]  # Default input is index 1.

    app = _make_app()
    with TestClient(app) as c:
        with patch("src.api.routes.devices.sd.query_devices", return_value=mock_devices):
            with patch("src.api.routes.devices.sd.default", mock_default):
                resp = c.get("/api/devices", headers=_auth_headers())
                assert resp.status_code == 200
                data = resp.json()
                for dev in data["devices"]:
                    if dev["name"] == "Built-in Mic":
                        assert dev["is_default"] is True
                    else:
                        assert dev["is_default"] is False


def test_list_devices_empty():
    mock_devices = [
        {
            "name": "Speakers",
            "max_input_channels": 0,
            "max_output_channels": 2,
            "default_samplerate": 44100.0,
        },
    ]
    mock_default = MagicMock()
    mock_default.device = [0, 0]

    app = _make_app()
    with TestClient(app) as c:
        with patch("src.api.routes.devices.sd.query_devices", return_value=mock_devices):
            with patch("src.api.routes.devices.sd.default", mock_default):
                resp = c.get("/api/devices", headers=_auth_headers())
                assert resp.status_code == 200
                data = resp.json()
                assert data["devices"] == []


# ---------------------------------------------------------------------------
# Bug A6: defensive default-detection
# ---------------------------------------------------------------------------


def test_no_default_input_marks_no_device_as_default():
    """When sd.default.device returns (-1, -1) — i.e. no default input is
    configured — none of the listed devices should be flagged is_default.
    Today: the comparison i == -1 happens to give False for any positive
    i, so this works by accident. Lock it in as a regression guard."""
    mock_devices = [
        {
            "name": "USB Mic",
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 48000.0,
        },
        {
            "name": "Built-in Mic",
            "max_input_channels": 2,
            "max_output_channels": 0,
            "default_samplerate": 44100.0,
        },
    ]
    mock_default = MagicMock()
    mock_default.device = [-1, -1]

    app = _make_app()
    with TestClient(app) as c:
        with patch("src.api.routes.devices.sd.query_devices", return_value=mock_devices):
            with patch("src.api.routes.devices.sd.default", mock_default):
                resp = c.get("/api/devices", headers=_auth_headers())
                assert resp.status_code == 200
                data = resp.json()
                assert all(d["is_default"] is False for d in data["devices"])


def test_query_devices_failure_returns_empty_list_not_500():
    """When PortAudio init fails or sd.query_devices raises, the endpoint
    should degrade gracefully and return an empty list rather than 500.
    The Settings page still loads; the user sees "no devices found"
    instead of an opaque server error."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        with patch(
            "src.api.routes.devices.sd.query_devices",
            side_effect=RuntimeError("PortAudio not initialised"),
        ):
            resp = c.get("/api/devices", headers=_auth_headers())
            assert resp.status_code == 200, (
                f"PortAudio failure must not 500 the endpoint; got {resp.status_code}: {resp.text}"
            )
            assert resp.json() == {"devices": []}


def test_default_device_access_failure_does_not_crash_listing():
    """If reading sd.default.device raises (some sounddevice versions on
    headless / unusual configurations), the listing should still return
    the available inputs — just with is_default=False on all of them."""
    mock_devices = [
        {
            "name": "USB Mic",
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 48000.0,
        },
    ]
    broken_default = MagicMock()
    type(broken_default).device = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("no default device"))
    )

    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        with patch("src.api.routes.devices.sd.query_devices", return_value=mock_devices):
            with patch("src.api.routes.devices.sd.default", broken_default):
                resp = c.get("/api/devices", headers=_auth_headers())
                assert resp.status_code == 200, (
                    "default-device access failure must not 500; "
                    f"got {resp.status_code}: {resp.text}"
                )
                data = resp.json()
                assert len(data["devices"]) == 1
                assert data["devices"][0]["is_default"] is False
