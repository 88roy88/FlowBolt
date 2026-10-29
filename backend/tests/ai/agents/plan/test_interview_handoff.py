from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from flow44.ai.agents.plan import agent as plan_agent_module
from flow44.ai.agents.plan.agent import PlanAgent
from flow44.ai.agents.plan.plan_state import PlanState
from flow44.ai.state import BuildState
from flow44.db.project_data_source import DataSourceContext


def _make_agent() -> PlanAgent:
    sandbox = SimpleNamespace(project_id="proj-1")
    agent = PlanAgent(project_id="proj-1", sandbox=sandbox, user_id="user-1")  # type: ignore[arg-type]
    agent._setup_trace = lambda tags: None  # type: ignore[method-assign, assignment]

    async def emit(event: dict[str, Any]) -> None:
        return None

    agent.emit = emit  # type: ignore[method-assign]
    return agent


class TestPrefetchDataSources:
    async def test_returns_state_carrying_fetched_contexts(self) -> None:
        agent = _make_agent()
        context = DataSourceContext(
            data_source_id="sales",
            data_source_name="Sales",
            sanitized_name="Sales",
            data_schema="Revenue by date",
            relevant_fields="date, revenue",
        )

        async def _fetch(state: PlanState) -> PlanState:
            agent._state.data_source_contexts = [context]
            return state

        agent._step_fetch_data_sources = _fetch  # type: ignore[method-assign]

        state = await agent.prefetch_data_sources("build a dashboard", ["sales"])

        assert state.user_content == "build a dashboard"
        assert state.data_source_ids == ["sales"]
        assert state.data_source_contexts == [context]

    async def test_skips_the_fetch_without_data_sources(self) -> None:
        agent = _make_agent()
        fetched: list[str] = []

        async def _fetch(state: PlanState) -> PlanState:
            fetched.append("fetch")
            return state

        agent._step_fetch_data_sources = _fetch  # type: ignore[method-assign]

        state = await agent.prefetch_data_sources("build a red button")

        assert fetched == []
        assert state.data_source_contexts == []


class TestRunFromDesign:
    async def test_adopts_the_state_and_enters_the_flow_at_design(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent = _make_agent()
        ran: list[str | None] = []

        async def _run_flow(start: str | None = None) -> None:
            ran.append(start)

        agent._run_flow = _run_flow  # type: ignore[method-assign]

        state = BuildState(project_id="proj-1", user_content="original")
        await agent.run_from_design("build a dashboard\n\nClarifications", state.model_dump_json())

        assert ran == ["design"]
        assert agent._state.project_id == "proj-1"
        assert agent._state.user_content == "build a dashboard\n\nClarifications"
        assert agent._state.model == agent.model


class TestPersist:
    async def test_pauses_the_turn_as_awaiting_approval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent = _make_agent()
        paused: list[tuple[str, str, str]] = []

        async def _pause(project_id: str, phase: str, state_json: str) -> None:
            paused.append((project_id, phase, state_json))

        monkeypatch.setattr(plan_agent_module, "pause_turn", _pause)

        await agent._step_persist(agent._make_plan_state())

        assert paused == [("proj-1", "awaiting_approval", agent._state.model_dump_json())]
