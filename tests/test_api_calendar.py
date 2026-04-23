"""Tests for the calendar meeting query endpoint."""


import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import src.api.auth as auth_mod
from src.api.auth import verify_token
from src.api.routes import calendar as calendar_routes
from src.db.database import Database
from src.db.repository import MeetingRepository

TEST_TOKEN = "test-calendar-token"


def _make_app(repo) -> FastAPI:
    calendar_routes.init(repo)
    app = FastAPI()
    app.include_router(calendar_routes.router, dependencies=[Depends(verify_token)])
    return app


def _auth_headers():
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture(autouse=True)
def _reset_repo():
    original = calendar_routes._repo
    yield
    calendar_routes._repo = original


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
async def test_calendar_meetings_returns_meetings_in_range(client):
    """Meetings within the queried range are returned; outside are excluded."""
    c, repo = client

    base = 1_700_000_000.0
    # inside range
    mid1 = await repo.create_meeting(started_at=base + 100)
    mid2 = await repo.create_meeting(started_at=base + 200)
    # outside range (before start)
    await repo.create_meeting(started_at=base - 100)

    start = base
    end = base + 300
    resp = c.get(
        "/api/calendar/meetings",
        params={"start": start, "end": end},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    returned_ids = {m["id"] for m in data["meetings"]}
    assert mid1 in returned_ids
    assert mid2 in returned_ids


@pytest.mark.asyncio
async def test_calendar_meetings_empty_range(client):
    """A range with no meetings returns an empty list and count=0."""
    c, repo = client

    base = 1_700_000_000.0
    await repo.create_meeting(started_at=base - 500)

    resp = c.get(
        "/api/calendar/meetings",
        params={"start": base, "end": base + 3600},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["meetings"] == []


@pytest.mark.asyncio
async def test_calendar_meetings_invalid_range(client):
    """end <= start returns 422."""
    c, _repo = client

    base = 1_700_000_000.0
    resp = c.get(
        "/api/calendar/meetings",
        params={"start": base + 100, "end": base},
        headers=_auth_headers(),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_calendar_meetings_range_too_large(client):
    """A range exceeding 366 days returns 422."""
    c, _repo = client

    base = 1_700_000_000.0
    big_range = 367 * 86400
    resp = c.get(
        "/api/calendar/meetings",
        params={"start": base, "end": base + big_range},
        headers=_auth_headers(),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_calendar_meetings_requires_auth(client):
    """Requests without an auth header are rejected with 401 or 403."""
    c, _repo = client

    base = 1_700_000_000.0
    resp = c.get(
        "/api/calendar/meetings",
        params={"start": base, "end": base + 3600},
    )
    assert resp.status_code in (401, 403)
