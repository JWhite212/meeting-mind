"""Tests for the template CRUD API endpoints."""

from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import src.api.auth as auth_mod
from src.api.auth import verify_token
from src.api.routes import templates as templates_routes
from src.templates import TemplateManager

TEST_TOKEN = "test-token-templates"


def _make_app() -> FastAPI:
    app = FastAPI()
    auth_deps = [Depends(verify_token)]
    app.include_router(templates_routes.router, dependencies=auth_deps)
    return app


def _auth_headers():
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture
def client(tmp_path):
    original = auth_mod._auth_token
    auth_mod._auth_token = TEST_TOKEN

    with patch(
        "src.api.routes.templates.TemplateManager",
        lambda: TemplateManager(templates_dir=tmp_path / "templates"),
    ):
        app = _make_app()
        with TestClient(app) as c:
            yield c

    auth_mod._auth_token = original


def test_list_templates_returns_builtins(client):
    resp = client.get("/api/templates", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 5
    names = {t["name"] for t in data}
    assert "standard" in names
    assert "standup" in names


def test_get_template_standard(client):
    resp = client.get("/api/templates/standard", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "standard"
    assert len(data["system_prompt"]) > 0


def test_get_template_not_found(client):
    resp = client.get("/api/templates/nonexistent", headers=_auth_headers())
    assert resp.status_code == 404


def test_create_template(client):
    body = {
        "name": "my-custom",
        "description": "Test template",
        "system_prompt": "You are a test summariser.",
        "sections": ["Section A", "Section B"],
    }
    resp = client.post("/api/templates", json=body, headers=_auth_headers())
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "my-custom"
    assert data["sections"] == ["Section A", "Section B"]


def test_delete_template(client):
    # Create first.
    body = {
        "name": "to-delete",
        "description": "Will be deleted",
        "system_prompt": "Prompt.",
        "sections": ["S1"],
    }
    client.post("/api/templates", json=body, headers=_auth_headers())

    resp = client.delete("/api/templates/to-delete", headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


def test_delete_nonexistent_template(client):
    resp = client.delete("/api/templates/nonexistent", headers=_auth_headers())
    assert resp.status_code == 404
