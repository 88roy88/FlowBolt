from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from flow44.ai.agents.interview import agent as interview_agent_module
from flow44.ai.agents.interview.agent import InterviewAgent
from flow44.ai.agents.interview.models import InterviewAnswer, InterviewOption, InterviewQuestion, InterviewSession
from flow44.db.chat import ChatRole
from flow44.db.project_data_source import DataSourceContext


def _question(qid: str = "q-1", question: str = "Who is this for?") -> InterviewQuestion:
    return InterviewQuestion(
        id=qid,
        header="Audience",
        question=question,
        options=[InterviewOption(label="Me", description="Personal use"), InterviewOption(label="Team")],
    )


@pytest.fixture
def deps(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    deps = SimpleNamespace(
        emit=AsyncMock(),
        pause=AsyncMock(),
        fetch=AsyncMock(return_value=[]),
        chat=AsyncMock(return_value=json.dumps({"questions": []})),
        save=AsyncMock(),
    )
    monkeypatch.setattr(interview_agent_module, "save_message", deps.save)
    monkeypatch.setattr(interview_agent_module, "pause_turn", deps.pause)
    monkeypatch.setattr(interview_agent_module, "fetch_data_sources", deps.fetch)
    monkeypatch.setattr(interview_agent_module, "complete_chat", deps.chat)
    return deps


@pytest.fixture
def agent(deps: SimpleNamespace) -> InterviewAgent:
    sandbox = SimpleNamespace(project_id="proj-1")
    agent = InterviewAgent(project_id="proj-1", sandbox=sandbox, user_id="user-1")  # type: ignore[arg-type]
    agent._setup_trace = lambda tags: None  # type: ignore[method-assign, assignment]
    agent.emit = deps.emit  # type: ignore[method-assign]
    return agent


def _events(deps: SimpleNamespace) -> list[dict[str, object]]:
    return [call.args[0] for call in deps.emit.await_args_list]


class TestAsk:
    async def test_pauses_with_the_questions(self, agent: InterviewAgent, deps: SimpleNamespace) -> None:
        deps.chat.return_value = json.dumps({"questions": [_question().model_dump()]})

        session = await agent.ask("build something")

        assert session.questions == [_question()]
        deps.fetch.assert_not_awaited()
        deps.pause.assert_awaited_once_with("proj-1", "awaiting_interview", session.model_dump_json())
        assert _events(deps) == [
            {"type": "phase", "phase": "interviewing"},
            {"type": "phase", "phase": "awaiting_interview"},
            {"type": "interview_questions", "questions": [_question().model_dump()]},
        ]

    async def test_no_questions_returns_without_pausing(self, agent: InterviewAgent, deps: SimpleNamespace) -> None:
        session = await agent.ask("build a red button")

        assert session.questions == []
        deps.pause.assert_not_awaited()
        assert _events(deps) == [{"type": "phase", "phase": "interviewing"}]

    async def test_data_sources_reach_the_prompt_and_the_session(
        self, agent: InterviewAgent, deps: SimpleNamespace
    ) -> None:
        context = DataSourceContext(
            data_source_id="sales", data_source_name="Sales", sanitized_name="Sales", relevant_fields="date, revenue"
        )
        deps.fetch.return_value = [context]
        deps.chat.return_value = json.dumps({"questions": [_question().model_dump()]})

        session = await agent.ask("build a dashboard", ["sales"])

        assert deps.fetch.await_args.args[0] == ["sales"]
        messages, prompt = deps.chat.await_args.args
        assert messages[0].content == "build a dashboard"
        assert "Data Source: Sales" in prompt
        assert "date, revenue" in prompt
        assert session.data_source_ids == ["sales"]
        assert session.data_source_contexts == [context]

    @pytest.mark.parametrize("failing", ["fetch", "chat"])
    async def test_failure_propagates_without_pausing(
        self, agent: InterviewAgent, deps: SimpleNamespace, failing: str
    ) -> None:
        getattr(deps, failing).side_effect = RuntimeError("down")

        with pytest.raises(RuntimeError, match="down"):
            await agent.ask("build a dashboard", ["sales"])

        deps.pause.assert_not_awaited()

    @pytest.mark.parametrize(
        "payload",
        [{"questions": None}, {"questions": [{**_question().model_dump(), "options": [{"label": "Me"}]}]}],
        ids=["null", "single-option"],
    )
    async def test_invalid_payload_asks_nothing(
        self, agent: InterviewAgent, deps: SimpleNamespace, payload: object
    ) -> None:
        deps.chat.return_value = json.dumps(payload)

        assert (await agent.ask("build something")).questions == []


class TestApplyAnswers:
    async def test_folds_answers_into_the_request(self, agent: InterviewAgent, deps: SimpleNamespace) -> None:
        questions = [_question("q-1"), _question("q-2", "What look?"), _question("q-3", "Which colours?")]
        answers = [
            InterviewAnswer(question_id="q-1", values=["Me", "My team"]),
            InterviewAnswer(question_id="q-2", values=[]),
        ]

        content = await agent.apply_answers(InterviewSession(content="build a dashboard", questions=questions), answers)

        clarifications = (
            "Clarifications from the user:\n"
            "- Who is this for?: Me (Personal use), My team\n"
            "- What look?: no preference given — pick a sensible default\n"
            "- Which colours?: no preference given — pick a sensible default"
        )
        assert content == f"build a dashboard\n\n{clarifications}"
        deps.save.assert_awaited_once_with("proj-1", ChatRole.user, clarifications)
        deps.emit.assert_awaited_once_with(
            {
                "type": "interview_answered",
                "questions": [q.model_dump() for q in questions],
                "answers": [a.model_dump() for a in answers],
            }
        )

    async def test_skip_leaves_the_request_and_history_untouched(
        self, agent: InterviewAgent, deps: SimpleNamespace
    ) -> None:
        session = InterviewSession(content="build a dashboard", questions=[_question()])

        assert await agent.apply_answers(session, []) == "build a dashboard"
        deps.save.assert_not_awaited()
