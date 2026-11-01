from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from flow44.ai.agents.analyze_data_source import generate_data_source_files
from flow44.ai.agents.plan import agent as plan_agent_module
from flow44.ai.agents.plan.agent import PlanAgent
from flow44.db import project_data_source
from flow44.db.project_data_source import DataSourceContext


def _ctx() -> DataSourceContext:
    return DataSourceContext(
        data_source_id="sales",
        data_source_name="Sales",
        sanitized_name="Sales",
        params_info={"parameters": [], "require_any": False},
        queries=[
            {
                "name": "rows",
                "display_name": "Rows",
                "description": "",
                "fields": [{"name": "id", "display_name": "ID", "type": "int", "description": None}],
            }
        ],
        sample_data={"results": {"rows": [{"id": 1}]}},
    )


async def _passthrough(self: PlanAgent, state: Any) -> Any:
    return state


@pytest.fixture
def sandbox() -> SimpleNamespace:
    return SimpleNamespace(project_id="proj-1", write_file=AsyncMock())


@pytest.fixture
def pause(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr(plan_agent_module, "pause_turn", mock)
    return mock


@pytest.fixture
def update_sources(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr(project_data_source, "update_project_data_sources", mock)
    return mock


@pytest.fixture
def agent(
    monkeypatch: pytest.MonkeyPatch, sandbox: SimpleNamespace, pause: AsyncMock, update_sources: AsyncMock
) -> PlanAgent:
    monkeypatch.setattr(PlanAgent, "_step_design", _passthrough)
    monkeypatch.setattr(PlanAgent, "_step_build_overview", _passthrough)
    plan_agent = PlanAgent(project_id="proj-1", sandbox=sandbox, user_id="user-1")  # type: ignore[arg-type]
    plan_agent._setup_trace = lambda tags: None  # type: ignore[method-assign, assignment]
    plan_agent.emit = AsyncMock()  # type: ignore[method-assign]
    return plan_agent


async def test_run_with_contexts_skips_the_fetch_but_writes_and_saves(
    monkeypatch: pytest.MonkeyPatch, agent: PlanAgent, sandbox: SimpleNamespace, update_sources: AsyncMock
) -> None:
    async def _fetch(*_a: object, **_kw: object) -> list[DataSourceContext]:
        raise AssertionError("fetch_data_sources must not be called")

    monkeypatch.setattr(plan_agent_module, "fetch_data_sources", _fetch)
    ctx = _ctx()

    await agent.run("build", ["sales"], data_source_contexts=[ctx])

    written = {call.args[0] for call in sandbox.write_file.await_args_list}
    assert set(generate_data_source_files(ctx)) <= written
    update_sources.assert_awaited_once_with("proj-1", [ctx])


async def test_run_without_contexts_fetches_once(monkeypatch: pytest.MonkeyPatch, agent: PlanAgent) -> None:
    calls: list[list[str]] = []

    async def _fetch(ids: list[str], *_a: object, **_kw: object) -> list[DataSourceContext]:
        calls.append(ids)
        return [_ctx()]

    monkeypatch.setattr(plan_agent_module, "fetch_data_sources", _fetch)

    await agent.run("build", ["sales"])

    assert calls == [["sales"]]


async def test_persist_pauses_the_turn_as_awaiting_approval(agent: PlanAgent, pause: AsyncMock) -> None:
    await agent.run("build")

    pause.assert_awaited_once_with("proj-1", "awaiting_approval", agent._state.model_dump_json())
