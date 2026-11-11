from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from flow44.ai.agents.interview.models import InterviewAnswer, InterviewOption, InterviewQuestion, InterviewSession
from flow44.ai.agents.routing import AgentRouter
from flow44.db.paused_turn import clear_paused_turn
from flow44.main import app

client = TestClient(app, raise_server_exceptions=False)

SESSION = InterviewSession(
    content="build a todo app",
    model="claude-opus-5",
    questions=[
        InterviewQuestion(
            id="q-1",
            header="Audience",
            question="Who is this for?",
            options=[InterviewOption(label="Me"), InterviewOption(label="Team")],
        )
    ],
)
# _start_turn is mocked so a handled message sends no reply; this one's error reply marks the one before it as done.
SYNC = {"type": "interview_response", "action": "sync"}


def _send(messages: list[dict[str, Any]], phase: str = "awaiting_interview") -> tuple[dict[str, Any], AsyncMock]:
    project = MagicMock(id="proj-123", user_id="user-a")
    turn = MagicMock(phase=phase, state_json=SESSION.model_dump_json())
    with (
        patch("flow44.api.deps.db_get_project", new_callable=AsyncMock, return_value=project),
        patch("flow44.api.deps.get_project_member", new_callable=AsyncMock, return_value=object()),
        patch("flow44.api.deps.get_user_id", new_callable=AsyncMock, return_value="user-a"),
        patch("flow44.api.chat.sandbox_manager") as mgr,
        patch("flow44.api.chat.versioning.broadcast_current_version", new_callable=AsyncMock),
        patch("flow44.api.chat.subscribe", return_value=asyncio.Queue()),
        patch("flow44.api.chat.unsubscribe"),
        patch("flow44.api.chat.get_paused_turn", new_callable=AsyncMock, return_value=turn),
        patch("flow44.api.chat._start_turn", new_callable=AsyncMock) as start_turn,
    ):
        mgr.wake_sandbox = AsyncMock(return_value=MagicMock(project_id="proj-123"))
        with client.websocket_connect("/ws/chat/proj-123", headers={"cookie": "flow44_token=t"}) as ws:
            for message in messages:
                ws.send_json(message)
            reply = ws.receive_json()
    return reply, start_turn


def _started_turn(message: dict[str, Any]) -> Any:
    _, start_turn = _send([message, SYNC])
    start_turn.assert_awaited_once()
    return start_turn.call_args


@pytest.mark.parametrize(
    ("message", "phase", "error"),
    [
        ({"type": "plan_response", "action": "accept"}, "awaiting_interview", "No pending plan found"),
        ({"type": "interview_response", "action": "skip"}, "awaiting_approval", "No pending interview found"),
        ({"type": "interview_response", "action": "submitt"}, "awaiting_interview", "Invalid interview action"),
    ],
)
def test_rejected_response_starts_no_turn(message: dict[str, Any], phase: str, error: str) -> None:
    reply, start_turn = _send([message], phase)

    assert reply == {"type": "error", "message": error}
    start_turn.assert_not_awaited()


@pytest.mark.parametrize(("extra", "interview"), [({}, False), ({"mode": "interview"}, True)])
def test_message_mode_decides_the_interview(extra: dict[str, str], interview: bool) -> None:
    turn = _started_turn({"type": "message", "content": "build a todo app", **extra}).args[1]

    assert turn.func.__func__ is AgentRouter.handle_message
    assert turn.keywords["interview"] is interview


def test_submit_resumes_with_the_answers_and_clears_the_paused_turn() -> None:
    call = _started_turn(
        {"type": "interview_response", "action": "submit", "answers": [{"question_id": "q-1", "values": ["Me"]}]}
    )

    resume = call.args[1]
    assert resume.func.__func__ is AgentRouter.resume_interview
    assert resume.args == (SESSION, [InterviewAnswer(question_id="q-1", values=["Me"])])
    assert resume.keywords == {"model": "claude-opus-5"}
    assert call.kwargs["prepare"].func is clear_paused_turn
    assert call.kwargs["prepare"].args == ("proj-123",)


def test_skip_discards_answers_sent_by_the_client() -> None:
    call = _started_turn(
        {"type": "interview_response", "action": "skip", "answers": [{"question_id": "q-1", "values": ["Me"]}]}
    )

    assert call.args[1].args[1] == []
