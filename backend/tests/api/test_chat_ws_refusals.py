"""A refused turn must leave no trace — no chat row, no event, no destroyed pending plan (F-12)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from flow44.main import app
from flow44.services.versioning.service import PreviewActiveError

client = TestClient(app, raise_server_exceptions=False)

PROJECT_ID = "proj-refusals"
CLAIMED_AT = datetime(2026, 1, 1, tzinfo=UTC)


@contextmanager
def _connected(claim: AsyncMock) -> Iterator[dict[str, AsyncMock]]:
    """A live chat WS with every write path mocked, so only ordering is under test."""
    project = MagicMock()
    project.id = PROJECT_ID
    project.user_id = "user-a"
    writes = {
        "save_message": AsyncMock(),
        "emit_event": AsyncMock(),
        "delete_pending_plan": AsyncMock(),
    }
    with (
        patch("flow44.api.deps.db_get_project", new_callable=AsyncMock, return_value=project),
        patch("flow44.api.deps.get_user_id", return_value="user-a"),
        patch("flow44.api.chat.sandbox_manager") as mgr,
        patch("flow44.api.chat.versioning.broadcast_current_version", new_callable=AsyncMock),
        patch("flow44.api.chat.versioning.claim_run_unless_previewing", claim),
        patch("flow44.api.chat.save_message", writes["save_message"]),
        patch("flow44.api.chat.emit_event", writes["emit_event"]),
        patch("flow44.api.chat.delete_pending_plan", writes["delete_pending_plan"]),
    ):
        sandbox = MagicMock()
        sandbox.project_id = PROJECT_ID  # the agents validate this, and would mask the assertions below
        mgr.wake_sandbox = AsyncMock(return_value=sandbox)
        yield writes


def _send(payload: dict[str, Any], claim: AsyncMock) -> tuple[dict[str, Any], dict[str, AsyncMock]]:
    with _connected(claim) as writes:
        with client.websocket_connect(f"/ws/chat/{PROJECT_ID}", headers={"cookie": "flow44_token=t"}) as ws:
            ws.send_json(payload)
            try:
                reply = ws.receive_json()
            except WebSocketDisconnect:  # pragma: no cover - only on an unexpected teardown
                pytest.fail("socket closed instead of replying")
        return reply, writes


def test_message_refused_while_previewing_saves_nothing() -> None:
    reply, writes = _send({"type": "message", "content": "change the header"}, AsyncMock(side_effect=PreviewActiveError))

    writes["save_message"].assert_not_awaited()
    writes["emit_event"].assert_not_awaited()
    assert reply == {"type": "version_error", "message": "Restore this version before editing", "code": "previewing"}


def test_message_refused_as_busy_saves_nothing() -> None:
    reply, writes = _send({"type": "message", "content": "change the header"}, AsyncMock(return_value=None))

    writes["save_message"].assert_not_awaited()
    writes["emit_event"].assert_not_awaited()
    assert reply["type"] == "error"
    assert "already running" in reply["message"]


def test_fix_error_refused_while_previewing_saves_nothing() -> None:
    reply, writes = _send(
        {"type": "fix_error", "error_message": "boom"}, AsyncMock(side_effect=PreviewActiveError)
    )

    writes["save_message"].assert_not_awaited()
    assert reply == {"type": "version_error", "message": "Restore this version before editing", "code": "previewing"}


def test_refused_plan_accept_keeps_the_pending_plan() -> None:
    state = MagicMock()
    state.model = "claude-opus-5"
    with (
        patch("flow44.api.chat.get_pending_plan", new_callable=AsyncMock, return_value="{}"),
        patch("flow44.api.chat.BuildState") as build_state,
    ):
        build_state.model_validate_json.return_value = state
        reply, writes = _send(
            {"type": "plan_response", "action": "accept"}, AsyncMock(side_effect=PreviewActiveError)
        )

    writes["delete_pending_plan"].assert_not_awaited()
    assert reply == {"type": "version_error", "message": "Restore this version before editing", "code": "previewing"}


def test_run_claim_released_when_a_side_effect_raises() -> None:
    claim = AsyncMock(return_value=CLAIMED_AT)
    with _connected(claim) as writes:
        writes["save_message"].side_effect = RuntimeError("boom")
        with patch("flow44.api.chat.clear_heartbeat", new_callable=AsyncMock) as clear_heartbeat:
            with client.websocket_connect(f"/ws/chat/{PROJECT_ID}", headers={"cookie": "flow44_token=t"}) as ws:
                ws.send_json({"type": "message", "content": "change the header"})
                try:
                    reply = ws.receive_json()
                except WebSocketDisconnect:  # pragma: no cover - only on an unexpected teardown
                    pytest.fail("socket closed instead of replying")

    assert reply == {"type": "error", "message": "Internal server error"}
    clear_heartbeat.assert_awaited_once_with(PROJECT_ID, only_beat=CLAIMED_AT)
