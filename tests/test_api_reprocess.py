"""Tests for src/api/routes/reprocess.py — reprocess endpoint."""

import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import src.api.auth as auth_mod
from src.api.auth import verify_token
from src.api.routes import reprocess as reprocess_routes
from src.db.database import Database
from src.db.repository import MeetingRepository

TEST_TOKEN = "test-token-for-reprocess-tests"


def _make_app(repo) -> FastAPI:
    reprocess_routes.init(repo)
    app = FastAPI()
    auth_deps = [Depends(verify_token)]
    app.include_router(reprocess_routes.router, dependencies=auth_deps)
    return app


def _auth_headers():
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture(autouse=True)
def _reset_module_state():
    original_repo = reprocess_routes._repo
    original_in_flight = set(reprocess_routes._in_flight)
    yield
    reprocess_routes._repo = original_repo
    reprocess_routes._in_flight.clear()
    reprocess_routes._in_flight.update(original_in_flight)


@pytest.fixture
async def client(db: Database):
    original = auth_mod._auth_token
    auth_mod._auth_token = TEST_TOKEN
    repo = MeetingRepository(db)
    app = _make_app(repo)
    with TestClient(app) as c:
        yield c, repo
    auth_mod._auth_token = original


# ---------------------------------------------------------------------------
# POST /api/meetings/{meeting_id}/reprocess
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reprocess_meeting_not_found(client):
    """POST reprocess with an unknown meeting_id returns 404."""
    c, _repo = client
    resp = c.post("/api/meetings/nonexistent-id/reprocess", headers=_auth_headers())
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reprocess_no_audio(client):
    """POST reprocess when meeting exists but has no audio_path returns 400."""
    c, repo = client
    mid = await repo.create_meeting(started_at=time.time())
    # Meeting exists but audio_path is not set.
    resp = c.post(f"/api/meetings/{mid}/reprocess", headers=_auth_headers())
    assert resp.status_code == 400
    assert "audio" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reprocess_audio_path_missing_on_disk(client, tmp_path):
    """POST reprocess when audio_path is set but the file no longer exists returns 400."""
    c, repo = client
    mid = await repo.create_meeting(started_at=time.time())
    ghost_path = str(tmp_path / "gone.wav")
    # Intentionally do NOT create the file.
    await repo.update_meeting(mid, audio_path=ghost_path)
    resp = c.post(f"/api/meetings/{mid}/reprocess", headers=_auth_headers())
    assert resp.status_code == 400
    assert "audio" in resp.json()["detail"].lower()


def test_reprocess_repo_not_initialized():
    """POST reprocess returns 503 when init() was never called (repo is None)."""
    reprocess_routes._repo = None
    original = auth_mod._auth_token
    auth_mod._auth_token = TEST_TOKEN
    try:
        app = FastAPI()
        auth_deps = [Depends(verify_token)]
        app.include_router(reprocess_routes.router, dependencies=auth_deps)
        with TestClient(app) as c:
            resp = c.post("/api/meetings/any-id/reprocess", headers=_auth_headers())
            assert resp.status_code == 503
    finally:
        auth_mod._auth_token = original


@pytest.mark.asyncio
async def test_reprocess_conflict_when_in_flight(client, tmp_path):
    """POST reprocess returns 409 when the meeting is already being reprocessed."""
    c, repo = client
    mid = await repo.create_meeting(started_at=time.time())

    # Create a real audio file so the in-flight check is reached.
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"RIFF" + b"\x00" * 40)
    await repo.update_meeting(mid, audio_path=str(audio_file))

    # Simulate an in-flight reprocess for this meeting.
    reprocess_routes._in_flight.add(mid)

    resp = c.post(f"/api/meetings/{mid}/reprocess", headers=_auth_headers())
    assert resp.status_code == 409
