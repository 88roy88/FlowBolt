from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from flow44.ai.agents.plan.models import InterviewQuestion
from flow44.ai.state import BuildState
from flow44.main import app

client = TestClient(app, raise_server_exceptions=False)


def _mock_project(user_id: str = "user-a", project_id: str = "proj-123") -> MagicMock:
    project = MagicMock()
    project.id = project_id
    project.user_id = user_id
    return project


def _base_interview_question() -> InterviewQuestion:
    return InterviewQuestion(
        id="q-1",
        header="Audience",
        question="Who is this for?",
        options=[
            {"label": "Me", "description": "Personal use"},
            {"label": "Team", "description": "Internal users"},
        ],
        multi_select=False,
    )


def _connect_and_send(payload: dict[str, object], state: BuildState) -> dict[str, object]:
    return _connect_and_send_all([payload], state)[0]


def _connect_and_send_all(payloads: list[dict[str, object]], state: BuildState) -> list[dict[str, object]]:
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    sandbox = MagicMock()

    with (
        patch("flow44.api.deps.db_get_project", new_callable=AsyncMock, return_value=_mock_project()),
        patch("flow44.api.deps.get_project_member", new_callable=AsyncMock, return_value=object()),
        patch("flow44.api.deps.get_user_id", return_value="user-a"),
        patch("flow44.api.chat.sandbox_manager") as mock_mgr,
        patch("flow44.api.chat.subscribe", return_value=queue),
        patch("flow44.api.chat.unsubscribe"),
        patch("flow44.api.chat.get_pending_plan", new_callable=AsyncMock, return_value=state.model_dump_json()),
        patch("flow44.api.chat._start_agent", new_callable=AsyncMock) as mock_start_agent,
    ):
        mock_mgr.wake_sandbox = AsyncMock(return_value=sandbox)
        responses: list[dict[str, object]] = []
        with client.websocket_connect("/ws/chat/proj-123", headers={"cookie": "flow44_token=test-token"}) as ws:
            for payload in payloads:
                ws.send_json(payload)
                responses.append(ws.receive_json())
        assert mock_start_agent.await_count == 0
        return responses


def test_plan_response_rejected_while_awaiting_interview() -> None:
    state = BuildState(project_id="proj-123", phase="awaiting_interview")
    response = _connect_and_send({"type": "plan_response", "action": "accept"}, state)
    assert response == {"type": "error", "message": "Plan response is only allowed while awaiting approval"}


def test_interview_response_rejected_while_awaiting_approval() -> None:
    state = BuildState(project_id="proj-123", phase="awaiting_approval")
    response = _connect_and_send({"type": "interview_response", "action": "skip"}, state)
    assert response == {"type": "error", "message": "Interview response is only allowed while awaiting interview"}


def test_interview_response_rejects_invalid_action() -> None:
    state = BuildState(project_id="proj-123", phase="awaiting_interview")
    response = _connect_and_send({"type": "interview_response", "action": "submitt"}, state)
    assert response == {"type": "error", "message": "Invalid interview action"}


def test_interview_response_rejects_malformed_answer_payload() -> None:
    state = BuildState(project_id="proj-123", phase="awaiting_interview")
    state.interview_questions = [_base_interview_question()]
    response = _connect_and_send(
        {"type": "interview_response", "action": "submit", "answers": [{"values": ["Me"]}]},
        state,
    )
    assert response["type"] == "error"
    assert str(response["message"]).startswith("Invalid payload:")


def test_non_iterable_answers_do_not_kill_the_session() -> None:
    state = BuildState(project_id="proj-123", phase="awaiting_interview")
    responses = _connect_and_send_all(
        [
            {"type": "interview_response", "action": "submit", "answers": 5},
            {"type": "interview_response", "action": "submitt"},
        ],
        state,
    )
    assert responses[0] == {"type": "error", "message": "Invalid payload"}
    assert responses[1] == {"type": "error", "message": "Invalid interview action"}
