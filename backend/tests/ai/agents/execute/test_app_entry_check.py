"""Tests for ExecuteAgent's check that the template App.tsx gets replaced."""

from __future__ import annotations

import pytest

from flow44.ai.agents.execute.agent import APP_ENTRY_PATH, APP_NOT_UPDATED_ERROR, ExecuteAgent
from flow44.ai.agents.execute.execution_state import ExecutionState
from flow44.ai.state import BuildState


class _Sandbox:
    async def read_file(self, path: str) -> str:
        return f"template {path}"


class _CleanBuildAgent(ExecuteAgent):
    async def _typecheck(self, state: ExecutionState) -> str:
        return ""

    async def _build(self, state: ExecutionState) -> str:
        return ""


def _make(completed_files: dict[str, str]) -> tuple[ExecuteAgent, ExecutionState]:
    build_state = BuildState(project_id="p")
    build_state.completed_files = completed_files
    state = ExecutionState(build_state=build_state, project_id="p", sandbox_ref=_Sandbox())
    return _CleanBuildAgent.__new__(_CleanBuildAgent), state


@pytest.mark.parametrize(
    ("completed_files", "expected_errors", "expected_route"),
    [
        ({"src/Foo.tsx": "FOO"}, APP_NOT_UPDATED_ERROR, "fix_errors"),
        ({"src/Foo.tsx": "FOO", APP_ENTRY_PATH: "APP"}, "", "summarize"),
    ],
)
async def test_validate_requires_app_update(
    completed_files: dict[str, str], expected_errors: str, expected_route: str
) -> None:
    agent, state = _make(completed_files)

    await agent._step_validate(state)

    assert state.all_errors == expected_errors
    assert agent._route_after_validate(state) == expected_route


async def test_files_for_fix_adds_current_app_from_sandbox() -> None:
    agent, state = _make({"src/Foo.tsx": "FOO"})

    files = await agent._files_for_fix(state)

    assert files == {"src/Foo.tsx": "FOO", APP_ENTRY_PATH: f"template {APP_ENTRY_PATH}"}
