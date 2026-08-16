"""Tests for the interview agent's clarifying questions and handoff."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from flow44.ai.agents.interview import agent as interview_agent_module
from flow44.ai.agents.interview.agent import InterviewAgent
from flow44.ai.agents.interview.models import InterviewAnswer, InterviewOption, InterviewQuestion
from flow44.ai.state import BuildState
from flow44.db.project_data_source import DataSourceContext


def _make_agent(monkeypatch: pytest.MonkeyPatch) -> tuple[InterviewAgent, list[dict[str, Any]], list[str]]:
    sandbox = SimpleNamespace(project_id="proj-1")
    agent = InterviewAgent(project_id="proj-1", sandbox=sandbox, user_id="user-1")  # type: ignore[arg-type]
    agent._setup_trace = lambda tags: None  # type: ignore[method-assign, assignment]  # noqa: ARG005

    emitted: list[dict[str, Any]] = []

    async def _emit(event: dict[str, Any]) -> None:
        emitted.append(event)

    agent.emit = _emit  # type: ignore[method-assign]

    saved: list[str] = []

    async def _save(_project_id: str, state_json: str) -> None:
        saved.append(state_json)

    monkeypatch.setattr(interview_agent_module, "save_pending_plan", _save)
    return agent, emitted, saved


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


class _Host:
    def __init__(self, state: BuildState | None = None) -> None:
        self.state = state or BuildState(project_id="proj-1")
        self.continued: list[BuildState] = []
        self.calls: list[str] = []

    async def gather_context(self, content: str, data_source_ids: list[str] | None = None) -> BuildState:
        self.calls.append("gather_context")
        self.state.user_content = content
        self.state.data_source_ids = data_source_ids or []
        return self.state

    async def continue_with(self, state: BuildState) -> None:
        self.calls.append("continue_with")
        self.continued.append(state)


def _stub_chat(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    async def _complete_chat(*_a: object, **_kw: object) -> str:
        return json.dumps(payload)

    monkeypatch.setattr(interview_agent_module, "complete_chat", _complete_chat)


class TestRun:
    async def test_generates_questions_and_pauses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, emitted, saved = _make_agent(monkeypatch)
        host = _Host()
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

        await agent.run("build something", gather_context=host.gather_context, continue_with=host.continue_with)

        assert host.continued == []
        assert saved, "a pending plan should be persisted while awaiting answers"
        state = BuildState.model_validate_json(saved[-1])
        assert state.phase == "awaiting_interview"
        assert [q.id for q in state.interview_questions] == ["q-1"]
        assert any(e["type"] == "interview_questions" for e in emitted)

    async def test_empty_questions_hands_over(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, emitted, saved = _make_agent(monkeypatch)
        host = _Host()
        _stub_chat(monkeypatch, {"questions": []})

        await agent.run("build a red button", gather_context=host.gather_context, continue_with=host.continue_with)

        assert host.continued == [host.state]
        assert saved == []
        assert not any(e["type"] == "interview_questions" for e in emitted)

    async def test_generation_failure_hands_over(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _saved = _make_agent(monkeypatch)
        host = _Host()

        async def _complete_chat(*_a: object, **_kw: object) -> str:
            raise RuntimeError("llm down")

        monkeypatch.setattr(interview_agent_module, "complete_chat", _complete_chat)

        await agent.run("build something", gather_context=host.gather_context, continue_with=host.continue_with)

        assert host.continued == [host.state]

    async def test_invalid_payload_hands_over(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _saved = _make_agent(monkeypatch)
        host = _Host()
        _stub_chat(monkeypatch, {"questions": None})

        await agent.run("build something", gather_context=host.gather_context, continue_with=host.continue_with)

        assert host.continued == [host.state]

    async def test_only_malformed_questions_hands_over(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _saved = _make_agent(monkeypatch)
        host = _Host()
        _stub_chat(monkeypatch, {"questions": [_question("q-1", options=[{"label": "Me"}])]})

        await agent.run("build something", gather_context=host.gather_context, continue_with=host.continue_with)

        assert host.continued == [host.state]

    async def test_drops_only_the_malformed_question(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, saved = _make_agent(monkeypatch)
        host = _Host()
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

        await agent.run("build something", gather_context=host.gather_context, continue_with=host.continue_with)

        state = BuildState.model_validate_json(saved[-1])
        assert [q.id for q in state.interview_questions] == ["q-2"]

    async def test_truncates_to_four_questions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, saved = _make_agent(monkeypatch)
        host = _Host()
        _stub_chat(monkeypatch, {"questions": [_question(f"q-{n}") for n in range(1, 6)]})

        await agent.run("build something", gather_context=host.gather_context, continue_with=host.continue_with)

        state = BuildState.model_validate_json(saved[-1])
        assert [q.id for q in state.interview_questions] == ["q-1", "q-2", "q-3", "q-4"]

    async def test_clamps_options_instead_of_dropping_the_question(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, saved = _make_agent(monkeypatch)
        host = _Host()
        _stub_chat(monkeypatch, {"questions": [_question("q-1", options=[{"label": f"opt-{n}"} for n in range(1, 6)])]})

        await agent.run("build something", gather_context=host.gather_context, continue_with=host.continue_with)

        state = BuildState.model_validate_json(saved[-1])
        assert [o.label for o in state.interview_questions[0].options] == ["opt-1", "opt-2", "opt-3", "opt-4"]

    async def test_duplicate_question_ids_keep_the_first(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, saved = _make_agent(monkeypatch)
        host = _Host()
        _stub_chat(
            monkeypatch,
            {
                "questions": [
                    _question("q-1", question="Who is this for?"),
                    _question("q-1", question="What look are you going for?"),
                ]
            },
        )

        await agent.run("build something", gather_context=host.gather_context, continue_with=host.continue_with)

        state = BuildState.model_validate_json(saved[-1])
        assert [q.question for q in state.interview_questions] == ["Who is this for?"]

    async def test_gathers_context_before_generating_questions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, saved = _make_agent(monkeypatch)
        context = DataSourceContext(
            data_source_id="sales",
            data_source_name="Sales",
            sanitized_name="Sales",
            data_schema="Revenue by date",
            relevant_fields="date, revenue",
        )
        host = _Host()
        host.state.data_source_contexts = [context]
        order: list[str] = []

        async def _gather(content: str, data_source_ids: list[str] | None = None) -> BuildState:
            order.append("gather")
            return await host.gather_context(content, data_source_ids)

        async def _generate(_state: BuildState) -> list[InterviewQuestion]:
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
            "build a dashboard", ["sales"], gather_context=_gather, continue_with=host.continue_with
        )

        assert order == ["gather", "generate"]
        persisted = BuildState.model_validate_json(saved[-1])
        assert persisted.data_source_contexts == [context]

    async def test_generation_includes_data_source_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _saved = _make_agent(monkeypatch)
        state = BuildState(project_id="proj-1", user_content="build a dashboard")
        state.data_source_contexts = [
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

        assert await agent._generate_questions(state) == []
        user_message, prompt = captured[0]
        assert user_message == "build a dashboard"
        assert "Data Source: Sales" in prompt
        assert "date, revenue" in prompt


class TestResume:
    async def test_folds_answers_and_hands_over(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, emitted, saved = _make_agent(monkeypatch)
        host = _Host()

        state = BuildState(project_id="proj-1", user_content="build a dashboard")
        state.interview_questions = [
            InterviewQuestion(
                id="q-1",
                header="Audience",
                question="Who is this for?",
                options=[
                    InterviewOption(label="Me", description="Personal use"),
                    InterviewOption(label="Team", description="Internal users"),
                ],
            )
        ]

        await agent.resume(state, [InterviewAnswer(question_id="q-1", values=["My team"])], continue_with=host.continue_with)

        assert host.continued == [state]
        assert saved == [], "the plan flow's persist step owns the save; an interim one is unreachable"
        assert state.interview_answers == [InterviewAnswer(question_id="q-1", values=["My team"])]
        assert "Who is this for?: My team" in state.user_content
        assert any(e["type"] == "interview_answered" for e in emitted)

    async def test_expands_option_description_and_marks_unanswered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _saved = _make_agent(monkeypatch)
        host = _Host()

        state = BuildState(project_id="proj-1", user_content="build a dashboard")
        state.interview_questions = [
            InterviewQuestion(
                id="q-1",
                header="Look",
                question="What look are you going for?",
                options=[
                    InterviewOption(label="Analytics-first", description="Dense tables, muted colours"),
                    InterviewOption(label="Playful", description="Big type, bright accents"),
                ],
            ),
            InterviewQuestion(
                id="q-2",
                header="Audience",
                question="Who is this for?",
                options=[
                    InterviewOption(label="Me", description="Personal use"),
                    InterviewOption(label="Team", description="Internal users"),
                ],
            ),
        ]

        await agent.resume(
            state, [InterviewAnswer(question_id="q-1", values=["Analytics-first"])], continue_with=host.continue_with
        )

        assert "Analytics-first (Dense tables, muted colours)" in state.user_content
        assert "Who is this for?: no preference given" in state.user_content

    async def test_skip_leaves_request_untouched(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _saved = _make_agent(monkeypatch)
        host = _Host()

        state = BuildState(project_id="proj-1", user_content="build a dashboard")
        await agent.resume(state, [], continue_with=host.continue_with)

        assert state.user_content == "build a dashboard"
        assert host.continued == [state]
