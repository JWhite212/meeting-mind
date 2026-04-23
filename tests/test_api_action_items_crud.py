"""Tests for action item CRUD API endpoints."""

import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import src.api.auth as auth_mod
from src.action_items.repository import ActionItemRepository
from src.api.auth import verify_token
from src.api.routes import action_items as ai_routes
from src.db.database import Database
from src.db.repository import MeetingRepository

TEST_TOKEN = "test-action-items-token"


def _make_app(repo) -> FastAPI:
    ai_routes.init(repo)
    app = FastAPI()
    auth_deps = [Depends(verify_token)]
    app.include_router(ai_routes.router, dependencies=auth_deps)
    return app


def _auth_headers():
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture(autouse=True)
def _reset_repo():
    original = ai_routes._repo
    yield
    ai_routes._repo = original


@pytest.fixture
async def client(db: Database):
    original = auth_mod._auth_token
    auth_mod._auth_token = TEST_TOKEN
    meeting_repo = MeetingRepository(db)
    ai_repo = ActionItemRepository(db)
    app = _make_app(ai_repo)
    with TestClient(app) as c:
        yield c, ai_repo, meeting_repo
    auth_mod._auth_token = original


@pytest.mark.asyncio
async def test_create_action_item(client):
    """POST /api/action-items returns 201 with the created item fields."""
    c, _ai_repo, meeting_repo = client
    mid = await meeting_repo.create_meeting(started_at=time.time())

    resp = c.post(
        "/api/action-items",
        json={"meeting_id": mid, "title": "Write tests", "priority": "high"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["meeting_id"] == mid
    assert data["title"] == "Write tests"
    assert data["priority"] == "high"
    assert data["status"] == "open"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_action_item(client):
    """GET /api/action-items/{id} returns 200 with the item."""
    c, ai_repo, meeting_repo = client
    mid = await meeting_repo.create_meeting(started_at=time.time())
    item_id = await ai_repo.create(meeting_id=mid, title="Review PR")

    resp = c.get(f"/api/action-items/{item_id}", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == item_id
    assert data["title"] == "Review PR"


@pytest.mark.asyncio
async def test_get_action_item_not_found(client):
    """GET /api/action-items/{id} for unknown id returns 404."""
    c, _ai_repo, _meeting_repo = client
    resp = c.get("/api/action-items/does-not-exist", headers=_auth_headers())
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_action_items(client):
    """GET /api/action-items returns all created items."""
    c, ai_repo, meeting_repo = client
    mid = await meeting_repo.create_meeting(started_at=time.time())
    await ai_repo.create(meeting_id=mid, title="First task")
    await ai_repo.create(meeting_id=mid, title="Second task")

    resp = c.get("/api/action-items", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) == 2
    titles = {item["title"] for item in data["items"]}
    assert titles == {"First task", "Second task"}


@pytest.mark.asyncio
async def test_update_action_item(client):
    """PATCH /api/action-items/{id} with status=done updates and returns item."""
    c, ai_repo, meeting_repo = client
    mid = await meeting_repo.create_meeting(started_at=time.time())
    item_id = await ai_repo.create(meeting_id=mid, title="Deploy service")

    resp = c.patch(
        f"/api/action-items/{item_id}",
        json={"status": "done"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == item_id
    assert data["status"] == "done"


@pytest.mark.asyncio
async def test_delete_action_item(client):
    """DELETE /api/action-items/{id} returns 204 and item is gone."""
    c, ai_repo, meeting_repo = client
    mid = await meeting_repo.create_meeting(started_at=time.time())
    item_id = await ai_repo.create(meeting_id=mid, title="To be deleted")

    resp = c.delete(f"/api/action-items/{item_id}", headers=_auth_headers())
    assert resp.status_code == 204

    gone = c.get(f"/api/action-items/{item_id}", headers=_auth_headers())
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_list_by_meeting(client):
    """GET /api/meetings/{id}/action-items returns only items for that meeting."""
    c, ai_repo, meeting_repo = client
    mid1 = await meeting_repo.create_meeting(started_at=time.time())
    mid2 = await meeting_repo.create_meeting(started_at=time.time())
    await ai_repo.create(meeting_id=mid1, title="Task A")
    await ai_repo.create(meeting_id=mid1, title="Task B")
    await ai_repo.create(meeting_id=mid2, title="Task C")

    resp = c.get(f"/api/meetings/{mid1}/action-items", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) == 2
    titles = {item["title"] for item in data["items"]}
    assert titles == {"Task A", "Task B"}
