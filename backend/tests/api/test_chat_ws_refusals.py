from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from flow44.db.events import emit_transient
from flow44.main import app
from flow44.services import run_abort
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
        "clear_paused_turn": AsyncMock(),
    }
    with (
        patch("flow44.api.deps.db_get_project", new_callable=AsyncMock, return_value=project),
        patch("flow44.api.deps.get_user_id", new_callable=AsyncMock, return_value="user-a"),
        patch("flow44.api.chat.sandbox_manager") as mgr,
        patch("flow44.api.chat.versioning.broadcast_current_version", new_callable=AsyncMock),
        patch("flow44.api.chat.versioning.begin_turn", claim),
        patch("flow44.api.chat.save_message", writes["save_message"]),
        patch("flow44.api.chat.emit_event", writes["emit_event"]),
        patch("flow44.api.chat.clear_paused_turn", writes["clear_paused_turn"]),
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


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "message", "content": "x" * 11},
        {"type": "plan_response", "action": "modify", "feedback": "x" * 11},
    ],
)
def test_text_over_the_length_limit_is_refused(payload: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("flow44.api.chat.settings.CHAT_MESSAGE_MAX_CHARS", 10)
    claim = AsyncMock(return_value=CLAIMED_AT)
    reply, writes = _send(payload, claim)

    claim.assert_not_awaited()
    writes["save_message"].assert_not_awaited()
    assert reply["type"] == "error"
    assert "too long" in reply["message"]


def test_refused_plan_accept_keeps_the_paused_turn() -> None:
    state = MagicMock()
    state.model = "claude-opus-5"
    turn = MagicMock(phase="awaiting_approval", state_json="{}")
    with (
        patch("flow44.api.chat.get_paused_turn", new_callable=AsyncMock, return_value=turn),
        patch("flow44.api.chat.BuildState") as build_state,
    ):
        build_state.model_validate_json.return_value = state
        reply, writes = _send({"type": "plan_response", "action": "accept"}, _locked("previewing"))

    writes["clear_paused_turn"].assert_not_awaited()
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


@pytest.mark.parametrize(
    ("payload", "phase"),
    [
        ({"type": "plan_response", "action": "accept"}, "awaiting_approval"),
        ({"type": "interview_response", "action": "skip"}, "awaiting_interview"),
    ],
)
def test_aborted_resume_pauses_the_turn_again(payload: dict[str, Any], phase: str) -> None:
    state_json = '{"plan": "build a todo app"}'
    state = MagicMock()
    state.model = "claude-opus-5"

    async def hang(*_args: Any, **_kwargs: Any) -> None:
        await emit_transient(PROJECT_ID, {"type": "agent_started"})
        await asyncio.sleep(30)

    turn = MagicMock(phase=phase, state_json=state_json)
    with (
        _connected(AsyncMock(return_value=CLAIMED_AT)) as writes,
        patch("flow44.api.chat.get_paused_turn", new_callable=AsyncMock, return_value=turn),
        patch("flow44.api.chat.BuildState") as build_state,
        patch("flow44.api.chat.InterviewSession") as interview_session,
        patch("flow44.api.chat.ExecuteAgent") as execute_agent,
        patch("flow44.api.chat.AgentRouter") as router,
        patch("flow44.api.chat.get_last_event_id", new_callable=AsyncMock, return_value=7),
        patch("flow44.api.chat.versioning.discard_agent_response", new_callable=AsyncMock) as discard,
        patch("flow44.api.chat.pause_turn", new_callable=AsyncMock) as pause_turn,
        patch("flow44.api.chat.clear_heartbeat", new_callable=AsyncMock),
        # The LISTEN/NOTIFY hop has its own test; here the abort wakes the run directly.
        patch.object(run_abort, "request_abort", AsyncMock(side_effect=run_abort._wake)),
    ):
        build_state.model_validate_json.return_value = state
        interview_session.model_validate_json.return_value = state
        execute_agent.return_value.run = hang
        router.return_value.resume_interview = hang
        with client.websocket_connect(f"/ws/chat/{PROJECT_ID}", headers={"cookie": "flow44_token=t"}) as ws:
            ws.send_json(payload)
            assert ws.receive_json() == {"type": "agent_started"}
            ws.send_json({"type": "abort"})
            assert ws.receive_json() == {"type": "turn_aborted"}

    writes["clear_paused_turn"].assert_awaited_once_with(PROJECT_ID)
    discard.assert_awaited_once_with(PROJECT_ID, 7, ANY)
    pause_turn.assert_awaited_once_with(PROJECT_ID, phase, state_json)
