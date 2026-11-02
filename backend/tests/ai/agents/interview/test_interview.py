from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from flow44.ai.agents.interview import agent as interview_agent_module
from flow44.ai.agents.interview.agent import InterviewAgent
from flow44.ai.agents.interview.models import (
    InterviewAnswer,
    InterviewOption,
    InterviewQuestion,
    InterviewSession,
)
from flow44.db.project_data_source import DataSourceContext


def _make_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[InterviewAgent, list[dict[str, Any]], list[tuple[str, str]]]:
    sandbox = SimpleNamespace(project_id="proj-1")
    agent = InterviewAgent(project_id="proj-1", sandbox=sandbox, user_id="user-1")  # type: ignore[arg-type]
    agent._setup_trace = lambda tags: None  # type: ignore[method-assign, assignment]

    emitted: list[dict[str, Any]] = []

    async def _emit(event: dict[str, Any]) -> None:
        emitted.append(event)

    agent.emit = _emit  # type: ignore[method-assign]

    paused: list[tuple[str, str]] = []

    async def _pause(_project_id: str, phase: str, state_json: str) -> None:
        paused.append((phase, state_json))

    async def _no_fetch(*_a: object, **_kw: object) -> list[DataSourceContext]:
        return []

    monkeypatch.setattr(interview_agent_module, "pause_turn", _pause)
    monkeypatch.setattr(interview_agent_module, "fetch_data_sources", _no_fetch)
    return agent, emitted, paused


def _question(qid: str) -> dict[str, Any]:
    return {
        "id": qid,
        "header": "Audience",
        "question": "Who is this for?",
        "options": [{"label": "Me", "description": "Personal use"}, {"label": "Team"}],
        "multi_select": False,
    }


def _stub_chat(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    async def _complete_chat(*_a: object, **_kw: object) -> str:
        return json.dumps(payload)

    monkeypatch.setattr(interview_agent_module, "complete_chat", _complete_chat)


def _paused_session(paused: list[tuple[str, str]]) -> InterviewSession:
    return InterviewSession.model_validate_json(paused[-1][1])


def _audience(qid: str = "q-1") -> InterviewQuestion:
    return InterviewQuestion(
        id=qid,
        header="Audience",
        question="Who is this for?",
        options=[
            InterviewOption(label="Me", description="Personal use"),
            InterviewOption(label="Team", description="Internal users"),
        ],
    )


class TestAsk:
    async def test_generates_questions_and_pauses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, emitted, paused = _make_agent(monkeypatch)
        _stub_chat(monkeypatch, {"questions": [_question("q-1")]})

        session = await agent.ask("build something")

        assert [q.id for q in session.questions] == ["q-1"]
        assert paused == [("awaiting_interview", session.model_dump_json())]
        assert any(e["type"] == "interview_questions" for e in emitted)

    async def test_empty_questions_returns_session_without_pausing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, emitted, paused = _make_agent(monkeypatch)
        _stub_chat(monkeypatch, {"questions": []})

        session = await agent.ask("build a red button")

        assert session.questions == []
        assert paused == []
        assert not any(e["type"] == "interview_questions" for e in emitted)

    async def test_fetches_contexts_once_before_generating_and_keeps_them(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agent, _emitted, paused = _make_agent(monkeypatch)
        context = DataSourceContext(
            data_source_id="sales",
            data_source_name="Sales",
            sanitized_name="Sales",
            data_schema="Revenue by date",
            relevant_fields="date, revenue",
        )
        order: list[str] = []

        async def _fetch(*_a: object, **_kw: object) -> list[DataSourceContext]:
            order.append("fetch")
            return [context]

        async def _generate(_content: str, _contexts: list[DataSourceContext]) -> list[InterviewQuestion]:
            order.append("generate")
            return [_audience()]

        monkeypatch.setattr(interview_agent_module, "fetch_data_sources", _fetch)
        agent._generate_questions = _generate  # type: ignore[method-assign]

        await agent.ask("build a dashboard", ["sales"])

        assert order == ["fetch", "generate"]
        assert _paused_session(paused).data_source_contexts == [context]
        assert _paused_session(paused).data_source_ids == ["sales"]

    async def test_no_data_sources_skips_the_fetch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _paused = _make_agent(monkeypatch)
        _stub_chat(monkeypatch, {"questions": []})
        fetched: list[str] = []

        async def _fetch(*_a: object, **_kw: object) -> list[DataSourceContext]:
            fetched.append("fetch")
            return []

        monkeypatch.setattr(interview_agent_module, "fetch_data_sources", _fetch)

        await agent.ask("build a red button")

        assert fetched == []

    async def test_fetch_failure_does_not_pause(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, emitted, paused = _make_agent(monkeypatch)

        async def _fetch(*_a: object, **_kw: object) -> list[DataSourceContext]:
            raise RuntimeError("flapi down")

        monkeypatch.setattr(interview_agent_module, "fetch_data_sources", _fetch)

        with pytest.raises(RuntimeError, match="flapi down"):
            await agent.ask("build a dashboard", ["sales"])

        assert paused == []
        assert not any(e.get("phase") == "interviewing" for e in emitted)

    async def test_generation_failure_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, paused = _make_agent(monkeypatch)

        async def _complete_chat(*_a: object, **_kw: object) -> str:
            raise RuntimeError("llm down")

        monkeypatch.setattr(interview_agent_module, "complete_chat", _complete_chat)

        with pytest.raises(RuntimeError, match="llm down"):
            await agent.ask("build something")

        assert paused == []

    async def test_invalid_payload_returns_no_questions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _paused = _make_agent(monkeypatch)
        _stub_chat(monkeypatch, {"questions": None})

        assert (await agent.ask("build something")).questions == []

    async def test_single_option_question_returns_no_questions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _paused = _make_agent(monkeypatch)
        _stub_chat(monkeypatch, {"questions": [{**_question("q-1"), "options": [{"label": "Me"}]}]})

        assert (await agent.ask("build something")).questions == []

    async def test_generation_includes_data_source_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _paused = _make_agent(monkeypatch)
        contexts = [
            DataSourceContext(
                data_source_id="sales",
                data_source_name="Sales",
                sanitized_name="Sales",
                data_schema="Revenue by date",
                relevant_fields="date, revenue",
                data_characteristics="Time series",
                params_info={"parameters": [{"name": "from_date"}]},
                param_ux_hints="Use a date picker",
                sample_data={"rows": [{"date": "2026-01-01", "revenue": 100}]},
            )
        ]
        captured: list[tuple[str, str]] = []

        async def _complete_chat(messages: list[object], prompt: str, *_args: object, **_kwargs: object) -> str:
            captured.append((str(getattr(messages[0], "content")), prompt))
            return json.dumps({"questions": []})

        monkeypatch.setattr(interview_agent_module, "complete_chat", _complete_chat)

        assert await agent._generate_questions("build a dashboard", contexts) == []
        user_message, prompt = captured[0]
        assert user_message == "build a dashboard"
        assert "Data Source: Sales" in prompt
        assert "date, revenue" in prompt


def _session(*questions: InterviewQuestion) -> InterviewSession:
    return InterviewSession(content="build a dashboard", questions=list(questions))


class TestApplyAnswers:
    async def test_folds_answers_into_the_content(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, emitted, paused = _make_agent(monkeypatch)

        answers = [InterviewAnswer(question_id="q-1", values=["My team"])]
        content = await agent.apply_answers(_session(_audience()), answers)

        assert content.startswith("build a dashboard\n\n")
        assert "Who is this for?: My team" in content
        assert paused == []
        assert any(e["type"] == "interview_answered" for e in emitted)

    async def test_expands_option_description_and_marks_unanswered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _paused = _make_agent(monkeypatch)

        look = InterviewQuestion(
            id="q-1",
            header="Look",
            question="What look are you going for?",
            options=[
                InterviewOption(label="Analytics-first", description="Dense tables, muted colours"),
                InterviewOption(label="Playful", description="Big type, bright accents"),
            ],
        )
        content = await agent.apply_answers(
            _session(look, _audience("q-2")), [InterviewAnswer(question_id="q-1", values=["Analytics-first"])]
        )

        assert "Analytics-first (Dense tables, muted colours)" in content
        assert "Who is this for?: no preference given" in content

    async def test_blank_submit_marks_every_question_unanswered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _paused = _make_agent(monkeypatch)

        questions = [
            InterviewQuestion(
                id=qid,
                header="H",
                question=text,
                options=[InterviewOption(label="A", description="a"), InterviewOption(label="B", description="b")],
            )
            for qid, text in (("q-1", "Who is this for?"), ("q-2", "What look?"))
        ]
        blank = [InterviewAnswer(question_id="q-1", values=[]), InterviewAnswer(question_id="q-2", values=[])]

        content = await agent.apply_answers(_session(*questions), blank)

        assert "Who is this for?: no preference given" in content
        assert "What look?: no preference given" in content

    async def test_skip_leaves_request_untouched(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _paused = _make_agent(monkeypatch)

        assert await agent.apply_answers(_session(_audience()), []) == "build a dashboard"
