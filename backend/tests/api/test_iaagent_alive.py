"""Tests for GET /api/iaagent/{project_id}/alive (heartbeat-derived liveness)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from flow44.api.deps import get_project
from flow44.config import settings
from flow44.db.events import AgentEvent
from flow44.db.heartbeat import AgentRunHeartbeat
from flow44.main import app

client = TestClient(app)
PROJECT_ID = "test-project-iaagent-alive"
mock_project = type("Project", (), {"id": PROJECT_ID})()


def setup_function() -> None:
    app.dependency_overrides[get_project] = lambda: mock_project


def teardown_function() -> None:
    app.dependency_overrides.pop(get_project, None)


def _event(payload: dict, *, _id: int = 1) -> AgentEvent:
    return AgentEvent(
        id=_id,
        project_id=PROJECT_ID,
        event_type=payload.get("type", "unknown"),
        payload=payload,
        created_at=datetime.now(UTC),
    )


def _heartbeat(*, age_seconds: float = 0.0) -> AgentRunHeartbeat:
    return AgentRunHeartbeat(
        project_id=PROJECT_ID,
        beat_at=datetime.now(UTC) - timedelta(seconds=age_seconds),
    )


def test_iaagent_alive_unknown_project() -> None:
    def _raise_404() -> None:
        raise HTTPException(status_code=404, detail="Project not found")

    app.dependency_overrides[get_project] = _raise_404
    response = client.get(f"/api/iaagent/{PROJECT_ID}/alive")
    assert response.status_code == 404


def test_iaagent_alive_idle_without_heartbeat() -> None:
    with patch("flow44.db.heartbeat.get_heartbeat", new_callable=AsyncMock, return_value=None):
        response = client.get(f"/api/iaagent/{PROJECT_ID}/alive")
    assert response.status_code == 200
    assert response.json() == {"alive": False, "phase": "idle"}


def test_iaagent_alive_active_reports_latest_phase() -> None:
    events = [_event({"type": "phase", "phase": "planning"})]
    with (
        patch("flow44.db.heartbeat.get_heartbeat", new_callable=AsyncMock, return_value=_heartbeat()),
        patch("flow44.api.iaagent.get_events", new_callable=AsyncMock, return_value=events),
    ):
        response = client.get(f"/api/iaagent/{PROJECT_ID}/alive")
    assert response.status_code == 200
    assert response.json() == {"alive": True, "phase": "planning"}


def test_iaagent_alive_false_with_stale_heartbeat() -> None:
    stale_hb = _heartbeat(age_seconds=settings.AGENT_RUN_STALE_TIMEOUT + 10)
    with patch("flow44.db.heartbeat.get_heartbeat", new_callable=AsyncMock, return_value=stale_hb):
        response = client.get(f"/api/iaagent/{PROJECT_ID}/alive")
    assert response.status_code == 200
    assert response.json() == {"alive": False, "phase": "idle"}


def test_iaagent_alive_is_read_only() -> None:
    """A stale heartbeat reports not-alive but /alive never reaps (the sweeper does)."""
    stale_hb = _heartbeat(age_seconds=settings.AGENT_RUN_STALE_TIMEOUT + 10)
    emit = AsyncMock()
    with (
        patch("flow44.db.heartbeat.get_heartbeat", new_callable=AsyncMock, return_value=stale_hb),
        patch("flow44.db.heartbeat.emit_event", emit),
        patch("flow44.db.heartbeat.clear_heartbeat", new_callable=AsyncMock) as clear,
    ):
        response = client.get(f"/api/iaagent/{PROJECT_ID}/alive")

    assert response.status_code == 200
    assert response.json()["alive"] is False
    emit.assert_not_awaited()
    clear.assert_not_awaited()
