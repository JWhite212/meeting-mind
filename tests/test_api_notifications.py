"""Tests for notification management API endpoints."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import src.api.auth as auth_mod
from src.api.auth import verify_token
from src.api.routes import notifications as notifications_routes
from src.db.database import Database
from src.notifications.repository import NotificationRepository

TEST_TOKEN = "test-notifications-token"


def _make_app(repo: NotificationRepository) -> FastAPI:
    notifications_routes.init(repo)
    app = FastAPI()
    app.include_router(notifications_routes.router, dependencies=[Depends(verify_token)])
    return app


def _auth_headers():
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture(autouse=True)
def _reset_repo():
    original = notifications_routes._repo
    yield
    notifications_routes._repo = original


@pytest.fixture
async def client(db: Database):
    original = auth_mod._auth_token
    auth_mod._auth_token = TEST_TOKEN
    repo = NotificationRepository(db)
    app = _make_app(repo)
    with TestClient(app) as c:
        yield c, repo
    auth_mod._auth_token = original


@pytest.mark.asyncio
async def test_list_notifications_empty(client):
    """GET /api/notifications with no data returns an empty list."""
    c, _repo = client
    resp = c.get("/api/notifications", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["notifications"] == []


@pytest.mark.asyncio
async def test_list_notifications_with_data(client):
    """Created notifications appear in the list response."""
    c, repo = client
    nid1 = await repo.create(
        type="action_item",
        title="Review PR",
        body="Please review the open pull request.",
        channel="in_app",
    )
    nid2 = await repo.create(
        type="prep_brief",
        title="Meeting prep",
        body="Upcoming meeting in 15 minutes.",
        channel="in_app",
    )

    resp = c.get("/api/notifications", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["notifications"]) == 2
    returned_ids = {n["id"] for n in data["notifications"]}
    assert nid1 in returned_ids
    assert nid2 in returned_ids


@pytest.mark.asyncio
async def test_unread_count_returns_zero(client):
    """GET /api/notifications/unread-count with no notifications returns 0."""
    c, _repo = client
    resp = c.get("/api/notifications/unread-count", headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


@pytest.mark.asyncio
async def test_dismiss_notification(client):
    """PATCH /api/notifications/{id} updates status to dismissed."""
    c, repo = client
    nid = await repo.create(
        type="action_item",
        title="Follow up",
        body="Send meeting notes.",
        channel="in_app",
    )

    resp = c.patch(
        f"/api/notifications/{nid}",
        json={"status": "dismissed"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "dismissed"

    # Unread count should now be 0 (the only notification was just dismissed).
    count_resp = c.get("/api/notifications/unread-count", headers=_auth_headers())
    assert count_resp.json()["count"] == 0


@pytest.mark.asyncio
async def test_dismiss_nonexistent_returns_200(client):
    """PATCH for an unknown notification ID returns 200 (silent no-op UPDATE)."""
    c, _repo = client
    resp = c.patch(
        "/api/notifications/nonexistent-id",
        json={"status": "dismissed"},
        headers=_auth_headers(),
    )
    # The route issues UPDATE ... WHERE id = ? which affects 0 rows silently.
    assert resp.status_code == 200
    assert resp.json()["status"] == "dismissed"
