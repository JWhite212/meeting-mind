"""Tests for meeting series CRUD API endpoints."""

import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import src.api.auth as auth_mod
from src.api.auth import verify_token
from src.api.routes import series as series_routes
from src.db.database import Database
from src.db.repository import MeetingRepository
from src.series.repository import SeriesRepository

TEST_TOKEN = "test-series-token"


def _make_app(repo) -> FastAPI:
    series_routes.init(repo)
    app = FastAPI()
    auth_deps = [Depends(verify_token)]
    app.include_router(series_routes.router, dependencies=auth_deps)
    return app


def _auth_headers():
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture(autouse=True)
def _reset_repo():
    original = series_routes._repo
    yield
    series_routes._repo = original


@pytest.fixture
async def client(db: Database):
    original = auth_mod._auth_token
    auth_mod._auth_token = TEST_TOKEN
    meeting_repo = MeetingRepository(db)
    series_repo = SeriesRepository(db)
    app = _make_app(series_repo)
    with TestClient(app) as c:
        yield c, series_repo, meeting_repo
    auth_mod._auth_token = original


@pytest.mark.asyncio
async def test_create_series(client):
    """POST /api/series returns 201 with the created series fields."""
    c, _series_repo, _meeting_repo = client

    resp = c.post(
        "/api/series",
        json={"title": "Weekly Sync"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Weekly Sync"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_series(client):
    """GET /api/series/{id} returns 200 with the series and its meetings list."""
    c, series_repo, _meeting_repo = client
    sid = await series_repo.create(title="Daily Standup", detection_method="manual")

    resp = c.get(f"/api/series/{sid}", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sid
    assert data["title"] == "Daily Standup"
    assert "meetings" in data


@pytest.mark.asyncio
async def test_get_series_not_found(client):
    """GET /api/series/{id} for unknown id returns 404."""
    c, _series_repo, _meeting_repo = client
    resp = c.get("/api/series/does-not-exist", headers=_auth_headers())
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_series(client):
    """GET /api/series returns all created series."""
    c, series_repo, _meeting_repo = client
    await series_repo.create(title="Sprint Review", detection_method="manual")
    await series_repo.create(title="Retrospective", detection_method="manual")

    resp = c.get("/api/series", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert "series" in data
    assert len(data["series"]) == 2
    titles = {s["title"] for s in data["series"]}
    assert titles == {"Sprint Review", "Retrospective"}


@pytest.mark.asyncio
async def test_update_series(client):
    """PATCH /api/series/{id} with a new title updates and returns the series."""
    c, series_repo, _meeting_repo = client
    sid = await series_repo.create(title="Old Title", detection_method="manual")

    resp = c.patch(
        f"/api/series/{sid}",
        json={"title": "New Title"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sid
    assert data["title"] == "New Title"


@pytest.mark.asyncio
async def test_delete_series(client):
    """DELETE /api/series/{id} returns 204 and series is gone."""
    c, series_repo, _meeting_repo = client
    sid = await series_repo.create(title="To Be Deleted", detection_method="manual")

    resp = c.delete(f"/api/series/{sid}", headers=_auth_headers())
    assert resp.status_code == 204

    gone = c.get(f"/api/series/{sid}", headers=_auth_headers())
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_link_meeting_to_series(client):
    """POST /api/series/{id}/meetings links a meeting and returns status linked."""
    c, series_repo, meeting_repo = client
    sid = await series_repo.create(title="Design Review", detection_method="manual")
    mid = await meeting_repo.create_meeting(started_at=time.time())

    resp = c.post(
        f"/api/series/{sid}/meetings",
        json={"meeting_id": mid},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "linked"

    # Confirm the meeting appears in the series.
    detail = c.get(f"/api/series/{sid}", headers=_auth_headers())
    assert detail.status_code == 200
    meetings = detail.json()["meetings"]
    assert any(m["id"] == mid for m in meetings)


@pytest.mark.asyncio
async def test_get_series_trends(client):
    """GET /api/series/{id}/trends returns trend data for linked meetings."""
    c, series_repo, meeting_repo = client
    sid = await series_repo.create(title="Trend Test Series", detection_method="manual")

    # Create two meetings with duration and word_count set, then link them.
    mid1 = await meeting_repo.create_meeting(started_at=time.time())
    mid2 = await meeting_repo.create_meeting(started_at=time.time())
    await meeting_repo.update_meeting(mid1, duration_seconds=1800.0, word_count=300)
    await meeting_repo.update_meeting(mid2, duration_seconds=2400.0, word_count=450)
    await series_repo.link_meeting(mid1, sid)
    await series_repo.link_meeting(mid2, sid)

    resp = c.get(f"/api/series/{sid}/trends", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["series_id"] == sid
    assert data["meeting_count"] == 2
    assert len(data["duration_trend"]) == 2
    assert len(data["word_count_trend"]) == 2
    assert data["avg_duration_minutes"] > 0
