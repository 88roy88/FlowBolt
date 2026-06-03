"""Tests for GET /api/iaagent/{project_id}/alive."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from flow44.ai.agent_runtime import mark_agent_finished, mark_agent_started, reset_agent_runtime
from flow44.main import app

client = TestClient(app)
PROJECT_ID = "test-project-iaagent-alive"


def setup_function() -> None:
    reset_agent_runtime()


def teardown_function() -> None:
    reset_agent_runtime()


def test_iaagent_alive_unknown_project() -> None:
    with patch("flow44.api.iaagent.get_project", new_callable=AsyncMock, return_value=None):
        response = client.get(f"/api/iaagent/{PROJECT_ID}/alive")
    assert response.status_code == 404


def test_iaagent_alive_idle() -> None:
    mock_project = type("Project", (), {"id": PROJECT_ID})()
    with (
        patch("flow44.api.iaagent.get_project", new_callable=AsyncMock, return_value=mock_project),
        patch("flow44.api.iaagent.get_events", new_callable=AsyncMock, return_value=[]),
    ):
        response = client.get(f"/api/iaagent/{PROJECT_ID}/alive")
    assert response.status_code == 200
    assert response.json() == {"alive": False, "phase": "idle"}


def test_iaagent_alive_active() -> None:
    mock_project = type("Project", (), {"id": PROJECT_ID})()
    mark_agent_started(PROJECT_ID)
    try:
        with (
            patch("flow44.api.iaagent.get_project", new_callable=AsyncMock, return_value=mock_project),
            patch("flow44.api.iaagent.get_events", new_callable=AsyncMock, return_value=[]),
        ):
            response = client.get(f"/api/iaagent/{PROJECT_ID}/alive")
        assert response.status_code == 200
        assert response.json() == {"alive": True, "phase": "idle"}
    finally:
        mark_agent_finished(PROJECT_ID)
