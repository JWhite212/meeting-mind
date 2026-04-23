"""Tests for src/api/routes/prep.py — prep briefing endpoints."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import src.api.auth as auth_mod
from src.api.auth import verify_token
from src.api.routes import prep as prep_routes
from src.db.database import Database
from src.prep.repository import PrepRepository

TEST_TOKEN = "test-token-for-prep-tests"


def _make_app(repo: PrepRepository, generator=None) -> FastAPI:
    prep_routes.init(repo, generator)
    app = FastAPI()
    auth_deps = [Depends(verify_token)]
    app.include_router(prep_routes.router, dependencies=auth_deps)
    return app


def _auth_headers():
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture(autouse=True)
def _reset_module_state():
    original_repo = prep_routes._repo
    original_gen = prep_routes._generator
    yield
    prep_routes._repo = original_repo
    prep_routes._generator = original_gen


@pytest.fixture
async def client(db: Database):
    original = auth_mod._auth_token
    auth_mod._auth_token = TEST_TOKEN
    repo = PrepRepository(db)
    app = _make_app(repo)
    with TestClient(app) as c:
        yield c, repo
    auth_mod._auth_token = original


# ---------------------------------------------------------------------------
# GET /api/prep/upcoming
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upcoming_no_briefing(client):
    """GET /api/prep/upcoming returns 204 when no briefings exist."""
    c, _repo = client
    resp = c.get("/api/prep/upcoming", headers=_auth_headers())
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_upcoming_returns_briefing(client):
    """GET /api/prep/upcoming returns 200 with a briefing when one exists."""
    c, repo = client
    await repo.create(
        content_markdown="# Prep\n\nSome context.",
        expires_at=time.time() + 3600,
    )
    resp = c.get("/api/prep/upcoming", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["content_markdown"] == "# Prep\n\nSome context."


# ---------------------------------------------------------------------------
# GET /api/prep/{meeting_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_briefing_by_meeting(client):
    """GET /api/prep/{meeting_id} returns 200 when a briefing exists for that meeting."""
    c, repo = client
    meeting_id = "meeting-abc-123"
    await repo.create(
        content_markdown="# Briefing for meeting",
        meeting_id=meeting_id,
        expires_at=time.time() + 3600,
    )
    resp = c.get(f"/api/prep/{meeting_id}", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["meeting_id"] == meeting_id
    assert data["content_markdown"] == "# Briefing for meeting"


@pytest.mark.asyncio
async def test_get_briefing_not_found(client):
    """GET /api/prep/{meeting_id} returns 404 for an unknown meeting_id."""
    c, _repo = client
    resp = c.get("/api/prep/unknown-meeting-id", headers=_auth_headers())
    assert resp.status_code == 404
    assert "briefing" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_briefing_expired_not_returned(client):
    """GET /api/prep/{meeting_id} returns 404 when the only briefing is expired."""
    c, repo = client
    meeting_id = "meeting-expired"
    await repo.create(
        content_markdown="Old briefing",
        meeting_id=meeting_id,
        expires_at=time.time() - 1,  # already expired
    )
    resp = c.get(f"/api/prep/{meeting_id}", headers=_auth_headers())
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/prep/{meeting_id}/generate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_no_generator(db: Database):
    """POST /api/prep/{meeting_id}/generate returns 503 when generator is None."""
    original = auth_mod._auth_token
    auth_mod._auth_token = TEST_TOKEN
    try:
        repo = PrepRepository(db)
        app = _make_app(repo, generator=None)
        with TestClient(app) as c:
            resp = c.post("/api/prep/some-meeting-id/generate", headers=_auth_headers())
            assert resp.status_code == 503
            assert "generator" in resp.json()["detail"].lower()
    finally:
        auth_mod._auth_token = original


@pytest.mark.asyncio
async def test_generate_with_generator(client):
    """POST /api/prep/{meeting_id}/generate returns 201 when generator succeeds."""
    c, repo = client
    meeting_id = "meeting-gen-test"

    # Pre-create a briefing for the generator to return.
    briefing_id = await repo.create(
        content_markdown="# Generated Briefing",
        meeting_id=meeting_id,
        expires_at=time.time() + 3600,
    )

    mock_generator = MagicMock()
    mock_generator.generate = AsyncMock(return_value=briefing_id)

    # Re-init with the mock generator.
    prep_routes.init(repo, mock_generator)

    resp = c.post(f"/api/prep/{meeting_id}/generate", headers=_auth_headers())
    assert resp.status_code == 201
    data = resp.json()
    assert data["content_markdown"] == "# Generated Briefing"
    mock_generator.generate.assert_called_once()


def test_generate_repo_not_initialized():
    """POST /api/prep/.../generate returns 503 when repo is None (init never called)."""
    prep_routes._repo = None
    original = auth_mod._auth_token
    auth_mod._auth_token = TEST_TOKEN
    try:
        app = FastAPI()
        auth_deps = [Depends(verify_token)]
        app.include_router(prep_routes.router, dependencies=auth_deps)
        with TestClient(app) as c:
            resp = c.post("/api/prep/any-id/generate", headers=_auth_headers())
            assert resp.status_code == 503
    finally:
        auth_mod._auth_token = original
