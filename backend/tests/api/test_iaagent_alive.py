"""Tests for GET /api/iaagent/{project_id}/alive."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from flow44.ai.agent_runtime import mark_agent_finished, mark_agent_started, reset_agent_runtime
from flow44.api.deps import get_project
from flow44.main import app

client = TestClient(app)
PROJECT_ID = "test-project-iaagent-alive"
mock_project = type("Project", (), {"id": PROJECT_ID})()


def setup_function() -> None:
    reset_agent_runtime()
    app.dependency_overrides[get_project] = lambda: mock_project


def teardown_function() -> None:
    reset_agent_runtime()
    app.dependency_overrides.pop(get_project, None)


def test_iaagent_alive_unknown_project() -> None:
    def _raise_404() -> None:
        raise HTTPException(status_code=404, detail="Project not found")

    app.dependency_overrides[get_project] = _raise_404
    response = client.get(f"/api/iaagent/{PROJECT_ID}/alive")
    assert response.status_code == 404


def test_iaagent_alive_idle() -> None:
    with patch("flow44.api.iaagent.get_events", new_callable=AsyncMock, return_value=[]):
        response = client.get(f"/api/iaagent/{PROJECT_ID}/alive")
    assert response.status_code == 200
    assert response.json() == {"alive": False, "phase": "idle"}


def test_iaagent_alive_active() -> None:
    mark_agent_started(PROJECT_ID)
    try:
        with patch("flow44.api.iaagent.get_events", new_callable=AsyncMock, return_value=[]):
            response = client.get(f"/api/iaagent/{PROJECT_ID}/alive")
        assert response.status_code == 200
        assert response.json() == {"alive": True, "phase": "idle"}
    finally:
        mark_agent_finished(PROJECT_ID)
