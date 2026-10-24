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
from flow44.services.versioning.service import WorkspaceLocked

client = TestClient(app, raise_server_exceptions=False)

PROJECT_ID = "proj-refusals"
CLAIMED_AT = datetime(2026, 1, 1, tzinfo=UTC)

PREVIEWING = {
    "type": "version_error",
    "code": "previewing",
    "message": "Restore this version before editing",
    "files": [],
}


@contextmanager
def _connected(claim: AsyncMock) -> Iterator[dict[str, AsyncMock]]:
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
        patch("flow44.api.deps.get_user_id", new_callable=AsyncMock, return_value="user-a"),
        patch("flow44.api.chat.sandbox_manager") as mgr,
        patch("flow44.api.chat.versioning.broadcast_current_version", new_callable=AsyncMock),
        patch("flow44.api.chat.versioning.begin_turn", claim),
        patch("flow44.api.chat._is_new_project", new_callable=AsyncMock, return_value=True),
        patch("flow44.api.chat.save_message", writes["save_message"]),
        patch("flow44.api.chat.emit_event", writes["emit_event"]),
        patch("flow44.api.chat.delete_pending_plan", writes["delete_pending_plan"]),
    ):
        sandbox = MagicMock()
        sandbox.project_id = PROJECT_ID
        mgr.wake_sandbox = AsyncMock(return_value=sandbox)
        yield writes


def _send(payload: dict[str, Any], claim: AsyncMock) -> tuple[dict[str, Any], dict[str, AsyncMock]]:
    with _connected(claim) as writes:
        with client.websocket_connect(f"/ws/chat/{PROJECT_ID}", headers={"cookie": "flow44_token=t"}) as ws:
            ws.send_json(payload)
            try:
                reply = ws.receive_json()
            except WebSocketDisconnect:  # pragma: no cover
                pytest.fail("socket closed instead of replying")
        return reply, writes


def _locked(code: str, files: list[str] | None = None) -> AsyncMock:
    return AsyncMock(side_effect=WorkspaceLocked(code, files))


@pytest.mark.parametrize(
    ("payload", "code", "files"),
    [
        ({"type": "message", "content": "change the header"}, "previewing", []),
        ({"type": "fix_error", "error_message": "boom"}, "previewing", []),
        ({"type": "message", "content": "change the header"}, "dirty_workspace", ["src/App.tsx"]),
        ({"type": "fix_error", "error_message": "boom"}, "dirty_workspace", ["src/App.tsx"]),
    ],
)
def test_message_and_fix_error_refusals_write_nothing(payload: dict[str, Any], code: str, files: list[str]) -> None:
    reply, writes = _send(payload, _locked(code, files))

    writes["save_message"].assert_not_awaited()
    writes["emit_event"].assert_not_awaited()
    expected = {
        "type": "version_error",
        "code": code,
        "message": "You have unsaved edits" if code == "dirty_workspace" else "Restore this version before editing",
        "files": files,
    }
    assert reply == expected


def test_message_refused_as_busy_saves_nothing() -> None:
    reply, writes = _send({"type": "message", "content": "change the header"}, AsyncMock(return_value=None))

    writes["save_message"].assert_not_awaited()
    writes["emit_event"].assert_not_awaited()
    assert reply["type"] == "error"
    assert "already running" in reply["message"]


def test_refused_plan_accept_keeps_the_pending_plan() -> None:
    state = MagicMock()
    state.model = "claude-opus-5"
    with (
        patch("flow44.api.chat.get_pending_plan", new_callable=AsyncMock, return_value="{}"),
        patch("flow44.api.chat.BuildState") as build_state,
    ):
        build_state.model_validate_json.return_value = state
        reply, writes = _send({"type": "plan_response", "action": "accept"}, _locked("previewing"))

    writes["delete_pending_plan"].assert_not_awaited()
    assert reply == PREVIEWING


def test_run_claim_released_when_a_side_effect_raises() -> None:
    claim = AsyncMock(return_value=CLAIMED_AT)
    with (
        _connected(claim) as writes,
        patch("flow44.api.chat.clear_heartbeat", new_callable=AsyncMock) as clear_heartbeat,
    ):
        writes["save_message"].side_effect = RuntimeError("boom")
        with client.websocket_connect(f"/ws/chat/{PROJECT_ID}", headers={"cookie": "flow44_token=t"}) as ws:
            ws.send_json({"type": "message", "content": "change the header"})
            try:
                reply = ws.receive_json()
            except WebSocketDisconnect:  # pragma: no cover
                pytest.fail("socket closed instead of replying")

    assert reply == {"type": "error", "message": "Internal server error"}
    clear_heartbeat.assert_awaited_once_with(PROJECT_ID, only_beat=CLAIMED_AT)


def test_version_op_refusal_reaches_the_client() -> None:
    with patch("flow44.api.chat.versioning.preview_version", _locked("run_active")):
        reply, _ = _send({"type": "preview_version", "commit_sha": "abc"}, AsyncMock(return_value=CLAIMED_AT))

    assert reply == {
        "type": "version_error",
        "code": "run_active",
        "message": "Can't edit while the AI is working",
        "files": [],
    }


MSG_ID = "11111111-1111-4111-8111-111111111111"
NEW_ID = "22222222-2222-4222-8222-222222222222"


def _run_then_barrier(payload: dict[str, Any], original: dict[str, Any]) -> dict[str, Any]:
    """Send `payload`, then a refused op whose reply proves the first one was fully handled."""
    event = MagicMock()
    event.payload = original
    mocks = {
        "rewind": AsyncMock(return_value=event),
        "start_agent": MagicMock(),
        "plan_agent": MagicMock(),
    }
    with (
        _connected(AsyncMock(return_value=CLAIMED_AT)) as writes,
        patch("flow44.api.chat.find_user_event", new_callable=AsyncMock, return_value=event),
        patch("flow44.api.chat.versioning.rewind_to_message", mocks["rewind"]),
        patch("flow44.api.chat.versioning.preview_version", _locked("run_active")),
        patch("flow44.api.chat._start_agent", mocks["start_agent"]),
        patch("flow44.api.chat.PlanAgent", mocks["plan_agent"]),
        patch("flow44.api.chat.ds_logic.get_display_name", new_callable=AsyncMock, return_value="Sales"),
        patch("flow44.api.chat.count_user_messages", new_callable=AsyncMock, return_value=1),
    ):
        with client.websocket_connect(f"/ws/chat/{PROJECT_ID}", headers={"cookie": "flow44_token=t"}) as ws:
            ws.send_json(payload)
            ws.send_json({"type": "preview_version", "commit_sha": "abc"})
            first = ws.receive_json()
        return {**writes, **mocks, "reply": first}


def test_message_is_stored_under_the_client_id() -> None:
    result = _run_then_barrier({"type": "message", "content": "hi", "message_id": MSG_ID}, {})

    result["save_message"].assert_awaited_once_with(PROJECT_ID, "user", "hi", message_id=MSG_ID)
    assert result["emit_event"].await_args.args[1]["message_id"] == MSG_ID


def test_regenerate_resends_the_original_with_its_data_sources() -> None:
    original = {"type": "user_message", "content": "build a CRM", "data_sources": [{"id": 3, "name": "Sales"}]}
    result = _run_then_barrier({"type": "rewind", "message_id": MSG_ID, "new_message_id": NEW_ID}, original)

    result["rewind"].assert_awaited_once_with(PROJECT_ID, MSG_ID)
    result["save_message"].assert_awaited_once_with(PROJECT_ID, "user", "build a CRM", message_id=NEW_ID)
    assert result["emit_event"].await_args.args[1]["data_sources"] == [{"id": 3, "name": "Sales"}]
    assert result["plan_agent"].return_value.run.call_args.kwargs == {"data_source_ids": ["3"]}
    result["start_agent"].assert_called_once()


def test_edit_sends_the_new_content() -> None:
    original = {"type": "user_message", "content": "build a CRM"}
    result = _run_then_barrier(
        {"type": "rewind", "message_id": MSG_ID, "new_message_id": NEW_ID, "content": "build a wiki"}, original
    )

    result["save_message"].assert_awaited_once_with(PROJECT_ID, "user", "build a wiki", message_id=NEW_ID)
    assert result["plan_agent"].return_value.run.call_args.args == ("build a wiki",)


def test_editing_a_fix_request_is_refused_without_rewinding() -> None:
    original = {"type": "user_message", "content": "", "error_fix_request": {"errorMessage": "boom"}}
    result = _run_then_barrier({"type": "rewind", "message_id": MSG_ID, "content": "x"}, original)

    assert result["reply"] == {"type": "error", "message": "An error fix request can only be regenerated"}
    result["rewind"].assert_not_awaited()
    result["save_message"].assert_not_awaited()
