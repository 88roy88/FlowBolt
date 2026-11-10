from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from flow44.ai.agents import routing
from flow44.ai.agents.followup.agent import FollowUpAgent
from flow44.ai.agents.interview.models import InterviewAnswer, InterviewOption, InterviewQuestion, InterviewSession
from flow44.ai.agents.plan.agent import PlanAgent
from flow44.ai.agents.routing import AgentRouter
from flow44.db.project_data_source import DataSourceContext

CTX = DataSourceContext(data_source_id="s", data_source_name="S", sanitized_name="S")
QUESTION = InterviewQuestion(
    id="q-1",
    header="Audience",
    question="Who is this for?",
    options=[InterviewOption(label="Me"), InterviewOption(label="Team")],
)


def _session(*questions: InterviewQuestion) -> InterviewSession:
    return InterviewSession(content="hi", data_source_ids=["s"], data_source_contexts=[CTX], questions=list(questions))


@pytest.fixture
def agents(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    plan_run = AsyncMock()
    followup_run = AsyncMock()
    interviewer = MagicMock(ask=AsyncMock(), apply_answers=AsyncMock(return_value="hi\n\nClarifications"))
    interview_cls = MagicMock(return_value=interviewer)
    is_new = AsyncMock(return_value=True)
    monkeypatch.setattr(PlanAgent, "__init__", lambda self, *a, **kw: None)
    monkeypatch.setattr(FollowUpAgent, "__init__", lambda self, *a, **kw: None)
    monkeypatch.setattr(PlanAgent, "run", plan_run)
    monkeypatch.setattr(FollowUpAgent, "run", followup_run)
    monkeypatch.setattr(routing, "InterviewAgent", interview_cls)
    monkeypatch.setattr(routing, "is_new_project", is_new)
    return SimpleNamespace(
        plan_run=plan_run,
        followup_run=followup_run,
        interviewer=interviewer,
        interview_cls=interview_cls,
        is_new=is_new,
    )


def _router() -> AgentRouter:
    return AgentRouter("p", MagicMock(project_id="p"), user_id="u", data_source_authorization=None)


async def test_build_mode_runs_plan_without_interview(agents: SimpleNamespace) -> None:
    await _router().handle_message("hi", ["s"], model=None, interview=False)

    agents.plan_run.assert_awaited_once_with("hi", ["s"])
    agents.interview_cls.assert_not_called()


async def test_interview_mode_pauses_when_there_are_questions(agents: SimpleNamespace) -> None:
    agents.interviewer.ask.return_value = _session(QUESTION)

    await _router().handle_message("hi", ["s"], model=None, interview=True)

    agents.interviewer.ask.assert_awaited_once_with("hi", ["s"])
    agents.plan_run.assert_not_awaited()


async def test_interview_without_questions_runs_plan_with_its_contexts(agents: SimpleNamespace) -> None:
    agents.interviewer.ask.return_value = _session()

    await _router().handle_message("hi", ["s"], model=None, interview=True)

    agents.plan_run.assert_awaited_once_with("hi", ["s"], data_source_contexts=[CTX])
    agents.is_new.assert_awaited_once()


async def test_interview_ignored_for_followup(agents: SimpleNamespace) -> None:
    agents.is_new.return_value = False

    await _router().handle_message("hi", ["s"], model=None, interview=True)

    agents.followup_run.assert_awaited_once_with("hi", ["s"])
    agents.interview_cls.assert_not_called()


async def test_resume_runs_plan_with_clarified_content_and_contexts(agents: SimpleNamespace) -> None:
    session = _session(QUESTION)
    answers = [InterviewAnswer(question_id="q-1", values=["Me"])]

    await _router().resume_interview(session, answers, model=None)

    agents.interviewer.apply_answers.assert_awaited_once_with(session, answers)
    agents.plan_run.assert_awaited_once_with("hi\n\nClarifications", ["s"], data_source_contexts=[CTX])


async def test_resume_routes_to_followup_when_project_is_no_longer_new(agents: SimpleNamespace) -> None:
    agents.is_new.return_value = False

    await _router().resume_interview(_session(QUESTION), [], model=None)

    agents.followup_run.assert_awaited_once_with("hi\n\nClarifications", ["s"])
    agents.plan_run.assert_not_awaited()
