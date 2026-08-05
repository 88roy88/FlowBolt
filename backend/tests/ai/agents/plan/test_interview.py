"""Tests for the plan agent's clarifying-question interview."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from flow44.ai.agents.plan import agent as plan_agent_module
from flow44.ai.agents.plan.agent import PlanAgent
from flow44.ai.agents.plan.models import InterviewAnswer, InterviewQuestion
from flow44.ai.state import BuildState
from flow44.db.project_data_source import DataSourceContext


def _make_agent(monkeypatch: pytest.MonkeyPatch) -> tuple[PlanAgent, list[dict[str, Any]], list[str]]:
    sandbox = SimpleNamespace(project_id="proj-1")
    agent = PlanAgent(project_id="proj-1", sandbox=sandbox, user_id="user-1")  # type: ignore[arg-type]
    agent._setup_trace = lambda _tags: None  # type: ignore[method-assign]

    emitted: list[dict[str, Any]] = []

    async def _emit(event: dict[str, Any]) -> None:
        emitted.append(event)

    agent.emit = _emit  # type: ignore[method-assign]

    saved: list[str] = []

    async def _save(_project_id: str, state_json: str) -> None:
        saved.append(state_json)

    monkeypatch.setattr(plan_agent_module, "save_pending_plan", _save)
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


def _stub_flow(agent: PlanAgent) -> list[str | None]:
    ran: list[str | None] = []

    async def _run_flow(start: str | None = None) -> None:
        ran.append(start)

    agent._run_flow = _run_flow  # type: ignore[method-assign]
    return ran


class TestRunInterview:
    async def test_generates_questions_and_pauses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, emitted, saved = _make_agent(monkeypatch)
        ran = _stub_flow(agent)

        async def _complete_chat(*_a: object, **_kw: object) -> str:
            return json.dumps(
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
                }
            )

        monkeypatch.setattr(plan_agent_module, "complete_chat", _complete_chat)

        await agent.run_interview("build something")

        assert ran == []
        assert saved, "a pending plan should be persisted while awaiting answers"
        state = BuildState.model_validate_json(saved[-1])
        assert state.phase == "awaiting_interview"
        assert [q.id for q in state.interview_questions] == ["q-1"]
        assert any(e["type"] == "interview_questions" for e in emitted)

    async def test_empty_questions_falls_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, emitted, saved = _make_agent(monkeypatch)
        ran = _stub_flow(agent)

        async def _complete_chat(*_a: object, **_kw: object) -> str:
            return json.dumps({"questions": []})

        monkeypatch.setattr(plan_agent_module, "complete_chat", _complete_chat)

        await agent.run_interview("build a red button")

        assert ran == ["design"]
        assert saved == []
        assert not any(e["type"] == "interview_questions" for e in emitted)

    async def test_generation_failure_falls_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _saved = _make_agent(monkeypatch)
        ran = _stub_flow(agent)

        async def _complete_chat(*_a: object, **_kw: object) -> str:
            raise RuntimeError("llm down")

        monkeypatch.setattr(plan_agent_module, "complete_chat", _complete_chat)

        await agent.run_interview("build something")

        assert ran == ["design"]

    async def test_invalid_payload_falls_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _saved = _make_agent(monkeypatch)
        ran = _stub_flow(agent)

        async def _complete_chat(*_a: object, **_kw: object) -> str:
            return json.dumps({"questions": None})

        monkeypatch.setattr(plan_agent_module, "complete_chat", _complete_chat)

        await agent.run_interview("build something")

        assert ran == ["design"]

    async def test_only_malformed_questions_falls_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _saved = _make_agent(monkeypatch)
        ran = _stub_flow(agent)

        async def _complete_chat(*_a: object, **_kw: object) -> str:
            return json.dumps({"questions": [_question("q-1", options=[{"label": "Me"}])]})

        monkeypatch.setattr(plan_agent_module, "complete_chat", _complete_chat)

        await agent.run_interview("build something")

        assert ran == ["design"]

    async def test_drops_only_the_malformed_question(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, saved = _make_agent(monkeypatch)
        _stub_flow(agent)

        async def _complete_chat(*_a: object, **_kw: object) -> str:
            return json.dumps(
                {
                    "questions": [
                        _question("q-1", options=[{"label": "Me"}]),
                        _question("q-2"),
                        {"id": "q-3", "header": "No question text"},
                    ]
                }
            )

        monkeypatch.setattr(plan_agent_module, "complete_chat", _complete_chat)

        await agent.run_interview("build something")

        state = BuildState.model_validate_json(saved[-1])
        assert [q.id for q in state.interview_questions] == ["q-2"]

    async def test_truncates_to_four_questions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, saved = _make_agent(monkeypatch)
        _stub_flow(agent)

        async def _complete_chat(*_a: object, **_kw: object) -> str:
            return json.dumps({"questions": [_question(f"q-{n}") for n in range(1, 6)]})

        monkeypatch.setattr(plan_agent_module, "complete_chat", _complete_chat)

        await agent.run_interview("build something")

        state = BuildState.model_validate_json(saved[-1])
        assert [q.id for q in state.interview_questions] == ["q-1", "q-2", "q-3", "q-4"]

    async def test_clamps_options_instead_of_dropping_the_question(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, saved = _make_agent(monkeypatch)
        _stub_flow(agent)

        async def _complete_chat(*_a: object, **_kw: object) -> str:
            return json.dumps({"questions": [_question("q-1", options=[{"label": f"opt-{n}"} for n in range(1, 6)])]})

        monkeypatch.setattr(plan_agent_module, "complete_chat", _complete_chat)

        await agent.run_interview("build something")

        state = BuildState.model_validate_json(saved[-1])
        assert [o.label for o in state.interview_questions[0].options] == ["opt-1", "opt-2", "opt-3", "opt-4"]

    async def test_duplicate_question_ids_keep_the_first(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, saved = _make_agent(monkeypatch)
        _stub_flow(agent)

        async def _complete_chat(*_a: object, **_kw: object) -> str:
            return json.dumps(
                {
                    "questions": [
                        _question("q-1", question="Who is this for?"),
                        _question("q-1", question="What look are you going for?"),
                    ]
                }
            )

        monkeypatch.setattr(plan_agent_module, "complete_chat", _complete_chat)

        await agent.run_interview("build something")

        state = BuildState.model_validate_json(saved[-1])
        assert [q.question for q in state.interview_questions] == ["Who is this for?"]

    async def test_fetches_data_sources_before_generating_questions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, saved = _make_agent(monkeypatch)
        events: list[str] = []
        context = DataSourceContext(
            data_source_id="sales",
            data_source_name="Sales",
            sanitized_name="Sales",
            data_schema="Revenue by date",
            relevant_fields="date, revenue",
        )

        async def _fetch(_state: object) -> object:
            events.append("fetch")
            agent._state.data_source_contexts = [context]
            return _state

        async def _generate() -> list[InterviewQuestion]:
            events.append("interview")
            return [
                InterviewQuestion(
                    id="q-1",
                    header="Metrics",
                    question="Which metric matters most?",
                    options=[
                        {"label": "Revenue", "description": "Sales totals"},
                        {"label": "Orders", "description": "Order count"},
                    ],
                )
            ]

        agent._step_fetch_data_sources = _fetch  # type: ignore[method-assign]
        agent._generate_interview_questions = _generate  # type: ignore[method-assign]

        await agent.run_interview("build a dashboard", data_source_ids=["sales"])

        assert events == ["fetch", "interview"]
        persisted = BuildState.model_validate_json(saved[-1])
        assert persisted.data_source_contexts == [context]

    async def test_interview_generation_includes_data_source_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _saved = _make_agent(monkeypatch)
        agent._state.user_content = "build a dashboard"
        agent._state.data_source_contexts = [
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

        monkeypatch.setattr(plan_agent_module, "complete_chat", _complete_chat)

        assert await agent._generate_interview_questions() == []
        user_message, prompt = captured[0]
        assert user_message == "build a dashboard"
        assert "Data Source: Sales" in prompt
        assert "date, revenue" in prompt


class TestResumeAfterInterview:
    async def test_folds_answers_persists_and_resumes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, emitted, saved = _make_agent(monkeypatch)
        ran = _stub_flow(agent)

        state = BuildState(project_id="proj-1", user_content="build a dashboard")
        state.interview_questions = [
            InterviewQuestion(
                id="q-1",
                header="Audience",
                question="Who is this for?",
                options=[
                    {"label": "Me", "description": "Personal use"},
                    {"label": "Team", "description": "Internal users"},
                ],
            )
        ]

        await agent.resume_after_interview(state, [InterviewAnswer(question_id="q-1", values=["My team"])])

        assert ran == ["design"]
        assert saved == [], "the flow's persist step owns the save; an interim one is unreachable"
        assert agent._state.interview_answers == [InterviewAnswer(question_id="q-1", values=["My team"])]
        assert agent._state.model == agent.model
        assert "Who is this for?: My team" in agent._state.user_content
        assert any(e["type"] == "interview_answered" for e in emitted)

    async def test_expands_option_description_and_marks_unanswered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _saved = _make_agent(monkeypatch)
        _stub_flow(agent)

        state = BuildState(project_id="proj-1", user_content="build a dashboard")
        state.interview_questions = [
            InterviewQuestion(
                id="q-1",
                header="Look",
                question="What look are you going for?",
                options=[
                    {"label": "Analytics-first", "description": "Dense tables, muted colours"},
                    {"label": "Playful", "description": "Big type, bright accents"},
                ],
            ),
            InterviewQuestion(
                id="q-2",
                header="Audience",
                question="Who is this for?",
                options=[
                    {"label": "Me", "description": "Personal use"},
                    {"label": "Team", "description": "Internal users"},
                ],
            ),
        ]

        await agent.resume_after_interview(state, [InterviewAnswer(question_id="q-1", values=["Analytics-first"])])

        assert "Analytics-first (Dense tables, muted colours)" in agent._state.user_content
        assert "Who is this for?: no preference given" in agent._state.user_content

    async def test_skip_leaves_request_untouched(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent, _emitted, _saved = _make_agent(monkeypatch)
        _stub_flow(agent)

        state = BuildState(project_id="proj-1", user_content="build a dashboard")
        await agent.resume_after_interview(state, [])

        assert agent._state.user_content == "build a dashboard"
