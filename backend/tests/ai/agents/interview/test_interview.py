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
from flow44.ai.state import BuildState
from flow44.db.project_data_source import DataSourceContext

PAUSED_STATE = '{"x": 1}'


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

    monkeypatch.setattr(interview_agent_module, "pause_turn", _pause)
    return agent, emitted, paused


def _question(
    qid: str, *, question: str = "Who is this for?", options: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    return {
        "id": qid,
        "header": "Audience",
        "question": question,
        "options": options or [{"label": "Me", "description": "Personal use"}, {"label": "Team"}],
        "multi_select": False,
    }


class _PausedAgent:
    def __init__(self, state: BuildState | None = None) -> None:
        self.state = state or BuildState(project_id="proj-1")
        self.continued: list[tuple[str, str]] = []

    async def gather_context(self, content: str, data_source_ids: list[str] | None = None) -> BuildState:
        self.state.user_content = content
        self.state.data_source_ids = data_source_ids or []
        return self.state

    async def continue_with(self, content: str, paused_state: str) -> None:
        self.continued.append((content, paused_state))


def _stub_chat(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    async def _complete_chat(*_a: object, **_kw: object) -> str:
        return json.dumps(payload)

    monkeypatch.setattr(interview_agent_module, "complete_chat", _complete_chat)


async def _run(agent: InterviewAgent, plan: _PausedAgent, content: str = "build something") -> None:
    await agent.run(content, gather_context=plan.gather_context, paused_agent="plan", continue_with=plan.continue_with)


def _paused_session(paused: list[tuple[str, str]]) -> InterviewSession:
    return InterviewSession.model_validate_json(paused[-1][1])


class TestRun:
    async def test_generates_questions_and_pauses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, emitted, paused = _make_agent(monkeypatch)
        plan = _PausedAgent()
        _stub_chat(
            monkeypatch,
            {
                "questions": [
                    {
                        "id": "q-1",
                        "header": "Audience",
                        "question": "Who is this for?",
                        "options": [
                            {"label": "Me", "description": "Personal use"},
                            {"label": "Team", "description": "Internal users"},
                        ],
                        "multi_select": False,
                    }
                ]
            },
        )

        await _run(agent, plan)

        assert plan.continued == []
        assert paused, "a paused turn should be persisted while awaiting answers"
        assert paused[-1][0] == "awaiting_interview"
        session = _paused_session(paused)
        assert session.paused_agent == "plan"
        assert session.content == "build something"
        assert session.paused_state == plan.state.model_dump_json()
        assert [q.id for q in session.questions] == ["q-1"]
        assert any(e["type"] == "interview_questions" for e in emitted)

    async def test_empty_questions_hands_over(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, emitted, paused = _make_agent(monkeypatch)
        plan = _PausedAgent()
        _stub_chat(monkeypatch, {"questions": []})

        await _run(agent, plan, "build a red button")

        assert plan.continued == [("build a red button", plan.state.model_dump_json())]
        assert paused == []
        assert not any(e["type"] == "interview_questions" for e in emitted)

    async def test_generation_failure_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _paused = _make_agent(monkeypatch)
        plan = _PausedAgent()

        async def _complete_chat(*_a: object, **_kw: object) -> str:
            raise RuntimeError("llm down")

        monkeypatch.setattr(interview_agent_module, "complete_chat", _complete_chat)

        with pytest.raises(RuntimeError, match="llm down"):
            await _run(agent, plan)

        assert plan.continued == []

    async def test_invalid_payload_hands_over(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _paused = _make_agent(monkeypatch)
        plan = _PausedAgent()
        _stub_chat(monkeypatch, {"questions": None})

        await _run(agent, plan)

        assert plan.continued == [("build something", plan.state.model_dump_json())]

    async def test_only_malformed_questions_hands_over(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _paused = _make_agent(monkeypatch)
        plan = _PausedAgent()
        _stub_chat(monkeypatch, {"questions": [_question("q-1", options=[{"label": "Me"}])]})

        await _run(agent, plan)

        assert plan.continued == [("build something", plan.state.model_dump_json())]

    async def test_drops_only_the_malformed_question(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, paused = _make_agent(monkeypatch)
        plan = _PausedAgent()
        _stub_chat(
            monkeypatch,
            {
                "questions": [
                    _question("q-1", options=[{"label": "Me"}]),
                    _question("q-2"),
                    {"id": "q-3", "header": "No question text"},
                ]
            },
        )

        await _run(agent, plan)

        assert [q.id for q in _paused_session(paused).questions] == ["q-2"]

    async def test_truncates_to_four_questions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, paused = _make_agent(monkeypatch)
        plan = _PausedAgent()
        _stub_chat(monkeypatch, {"questions": [_question(f"q-{n}") for n in range(1, 6)]})

        await _run(agent, plan)

        assert [q.id for q in _paused_session(paused).questions] == ["q-1", "q-2", "q-3", "q-4"]

    async def test_clamps_options_instead_of_dropping_the_question(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, paused = _make_agent(monkeypatch)
        plan = _PausedAgent()
        _stub_chat(monkeypatch, {"questions": [_question("q-1", options=[{"label": f"opt-{n}"} for n in range(1, 6)])]})

        await _run(agent, plan)

        options = _paused_session(paused).questions[0].options
        assert [o.label for o in options] == ["opt-1", "opt-2", "opt-3", "opt-4"]

    async def test_duplicate_question_ids_keep_the_first(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, paused = _make_agent(monkeypatch)
        plan = _PausedAgent()
        _stub_chat(
            monkeypatch,
            {
                "questions": [
                    _question("q-1", question="Who is this for?"),
                    _question("q-1", question="What look are you going for?"),
                ]
            },
        )

        await _run(agent, plan)

        assert [q.question for q in _paused_session(paused).questions] == ["Who is this for?"]

    async def test_gathers_context_before_generating_questions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, paused = _make_agent(monkeypatch)
        context = DataSourceContext(
            data_source_id="sales",
            data_source_name="Sales",
            sanitized_name="Sales",
            data_schema="Revenue by date",
            relevant_fields="date, revenue",
        )
        plan = _PausedAgent()
        plan.state.data_source_contexts = [context]
        order: list[str] = []

        async def _gather(content: str, data_source_ids: list[str] | None = None) -> BuildState:
            order.append("gather")
            return await plan.gather_context(content, data_source_ids)

        async def _generate(_content: str, _contexts: list[DataSourceContext]) -> list[InterviewQuestion]:
            order.append("generate")
            return [
                InterviewQuestion(
                    id="q-1",
                    header="Metrics",
                    question="Which metric matters most?",
                    options=[
                        InterviewOption(label="Revenue", description="Sales totals"),
                        InterviewOption(label="Orders", description="Order count"),
                    ],
                )
            ]

        agent._generate_questions = _generate  # type: ignore[method-assign]

        await agent.run(
            "build a dashboard",
            ["sales"],
            gather_context=_gather,
            paused_agent="plan",
            continue_with=plan.continue_with,
        )

        assert order == ["gather", "generate"]
        persisted = BuildState.model_validate_json(_paused_session(paused).paused_state)
        assert persisted.data_source_contexts == [context]

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
    return InterviewSession(
        content="build a dashboard", questions=list(questions), paused_agent="plan", paused_state=PAUSED_STATE
    )


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


class TestResume:
    async def test_folds_answers_and_hands_over(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, emitted, paused = _make_agent(monkeypatch)
        plan = _PausedAgent()

        answers = [InterviewAnswer(question_id="q-1", values=["My team"])]
        await agent.resume(_session(_audience()), answers, continue_with=plan.continue_with)

        content, paused_state = plan.continued[0]
        assert paused_state == PAUSED_STATE
        assert paused == [], "the continuation owns the next save; an interim one is unreachable"
        assert content.startswith("build a dashboard\n\n")
        assert "Who is this for?: My team" in content
        assert any(e["type"] == "interview_answered" for e in emitted)

    async def test_expands_option_description_and_marks_unanswered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _paused = _make_agent(monkeypatch)
        plan = _PausedAgent()

        look = InterviewQuestion(
            id="q-1",
            header="Look",
            question="What look are you going for?",
            options=[
                InterviewOption(label="Analytics-first", description="Dense tables, muted colours"),
                InterviewOption(label="Playful", description="Big type, bright accents"),
            ],
        )
        await agent.resume(
            _session(look, _audience("q-2")),
            [InterviewAnswer(question_id="q-1", values=["Analytics-first"])],
            continue_with=plan.continue_with,
        )

        content = plan.continued[0][0]
        assert "Analytics-first (Dense tables, muted colours)" in content
        assert "Who is this for?: no preference given" in content

    async def test_blank_submit_marks_every_question_unanswered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _paused = _make_agent(monkeypatch)
        plan = _PausedAgent()

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

        await agent.resume(_session(*questions), blank, continue_with=plan.continue_with)

        content = plan.continued[0][0]
        assert "Who is this for?: no preference given" in content
        assert "What look?: no preference given" in content

    async def test_skip_leaves_request_untouched(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _paused = _make_agent(monkeypatch)
        plan = _PausedAgent()

        await agent.resume(_session(_audience()), [], continue_with=plan.continue_with)

        assert plan.continued == [("build a dashboard", PAUSED_STATE)]
