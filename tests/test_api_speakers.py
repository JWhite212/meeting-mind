"""Tests for speaker name mapping API endpoints."""

import json
import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import src.api.auth as auth_mod
from src.api.auth import verify_token
from src.api.routes import speakers as speakers_routes
from src.db.database import Database
from src.db.repository import MeetingRepository

TEST_TOKEN = "test-token-speakers"


def _make_app(repo) -> FastAPI:
    speakers_routes.init(repo)
    app = FastAPI()
    auth_deps = [Depends(verify_token)]
    app.include_router(speakers_routes.router, dependencies=auth_deps)
    return app


def _auth_headers():
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture(autouse=True)
def _reset_repo():
    original = speakers_routes._repo
    yield
    speakers_routes._repo = original


@pytest.fixture
async def client(db: Database):
    original = auth_mod._auth_token
    auth_mod._auth_token = TEST_TOKEN
    repo = MeetingRepository(db)
    app = _make_app(repo)
    with TestClient(app) as c:
        yield c, repo
    auth_mod._auth_token = original


@pytest.mark.asyncio
async def test_set_speaker_name(client):
    """PATCH with display_name returns 200 with correct response."""
    c, repo = client
    mid = await repo.create_meeting(started_at=time.time())

    resp = c.patch(
        f"/api/meetings/{mid}/speakers/SPEAKER_00",
        json={"display_name": "Alice"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["meeting_id"] == mid
    assert data["speaker_id"] == "SPEAKER_00"
    assert data["display_name"] == "Alice"


@pytest.mark.asyncio
async def test_set_speaker_name_meeting_not_found(client):
    """PATCH for nonexistent meeting returns 404."""
    c, _repo = client
    resp = c.patch(
        "/api/meetings/nonexistent-id/speakers/SPEAKER_00",
        json={"display_name": "Alice"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_meeting_speakers(client):
    """Set a name then GET returns it."""
    c, repo = client
    mid = await repo.create_meeting(started_at=time.time())
    await repo.set_speaker_name(mid, "SPEAKER_00", "Alice")

    resp = c.get(f"/api/meetings/{mid}/speakers", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["speaker_id"] == "SPEAKER_00"
    assert data[0]["display_name"] == "Alice"
    assert data[0]["source"] == "manual"


@pytest.mark.asyncio
async def test_get_meeting_speakers_empty(client):
    """GET for meeting with no speakers returns empty list."""
    c, repo = client
    mid = await repo.create_meeting(started_at=time.time())

    resp = c.get(f"/api/meetings/{mid}/speakers", headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_meeting_speakers_not_found(client):
    """GET for nonexistent meeting returns 404."""
    c, _repo = client
    resp = c.get("/api/meetings/nonexistent-id/speakers", headers=_auth_headers())
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_global_speakers(client):
    """Set names across multiple meetings, GET /api/speakers returns all."""
    c, repo = client
    mid1 = await repo.create_meeting(started_at=time.time())
    mid2 = await repo.create_meeting(started_at=time.time())
    await repo.set_speaker_name(mid1, "SPEAKER_00", "Alice")
    await repo.set_speaker_name(mid2, "SPEAKER_01", "Bob")

    resp = c.get("/api/speakers", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {d["display_name"] for d in data}
    assert names == {"Alice", "Bob"}


@pytest.mark.asyncio
async def test_set_speaker_updates_transcript(client):
    """Setting a speaker name updates transcript_json labels."""
    c, repo = client
    mid = await repo.create_meeting(started_at=time.time())

    transcript_data = {
        "segments": [
            {"start": 0, "end": 5, "text": "Hello.", "speaker": "SPEAKER_00"},
            {"start": 5, "end": 10, "text": "Hi there.", "speaker": "SPEAKER_01"},
        ],
    }
    await repo.update_meeting(mid, transcript_json=json.dumps(transcript_data))

    resp = c.patch(
        f"/api/meetings/{mid}/speakers/SPEAKER_00",
        json={"display_name": "Alice"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200

    # Verify transcript_json was updated.
    meeting = await repo.get_meeting(mid)
    updated = json.loads(meeting.transcript_json)
    assert updated["segments"][0]["speaker"] == "Alice"
    assert updated["segments"][1]["speaker"] == "SPEAKER_01"
