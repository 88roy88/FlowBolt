"""Tests for ExecuteAgent platform file guard behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from flow44.ai.agents.execute.agent import ExecuteAgent
from flow44.ai.agents.execute.execution_state import ExecutionState
from flow44.ai.agents.execute.models import Task, WorkPlan
from flow44.ai.agents.plan.models import ArchitectureDesign, UXDesign
from flow44.ai.state import BuildState
from flow44.config import settings
from flow44.template_guard import load_protected_file_paths


def _minimal_work_plan(*, uses_routing: bool = False) -> WorkPlan:
    return WorkPlan(
        id="plan-1",
        summary="test",
        architecture=ArchitectureDesign(),
        ux_design=UXDesign(),
        tasks=[Task(id="task-1", title="App", description="", files=["src/App.tsx"])],
        uses_routing=uses_routing,
    )


@pytest.mark.asyncio
async def test_seed_platform_files_not_in_task_files() -> None:
    build_state = BuildState(project_id="p1", completed_files={}, task_files={})
    sandbox = MagicMock(project_id="p1")
    sandbox.read_file = AsyncMock(return_value="export function getRouterBasename() { return '/'; }")

    agent = ExecuteAgent("p1", sandbox, build_state)
    state = ExecutionState(
        build_state=build_state,
        project_id="p1",
        sandbox_ref=sandbox,
        emit_fn=AsyncMock(),
        model=None,
        trace_id=None,
        langfuse_client=MagicMock(),
        llm_metadata_fn=lambda _: {},
    )
    state.build_state.work_plan = _minimal_work_plan()

    await agent._seed_platform_files(state)

    assert "src/platform/routerBasename.ts" in state.build_state.completed_files
    assert state.build_state.task_files == {}


def test_platform_dependency_files_only_when_routing() -> None:
    build_state = BuildState(
        project_id="p1",
        completed_files={"src/platform/routerBasename.ts": "// platform"},
    )
    agent = ExecuteAgent("p1", MagicMock(project_id="p1"), build_state)
    state = ExecutionState(
        build_state=build_state,
        project_id="p1",
        sandbox_ref=MagicMock(project_id="p1"),
        emit_fn=AsyncMock(),
        model=None,
        trace_id=None,
        langfuse_client=MagicMock(),
        llm_metadata_fn=lambda _: {},
    )

    deps = agent._platform_dependency_files(state)
    assert deps == {"src/platform/routerBasename.ts": "// platform"}


def test_protected_paths_loaded_from_template() -> None:
    agent = ExecuteAgent("p1", MagicMock(project_id="p1"), BuildState(project_id="p1"))
    assert agent._protected_paths == frozenset(load_protected_file_paths(settings.TEMPLATE_DIR))
