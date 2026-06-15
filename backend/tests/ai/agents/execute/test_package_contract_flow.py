"""Regression tests for optional-package selection, installation, and planning order."""

from __future__ import annotations

from typing import Any

import pytest

import flow44.ai.agents.execute.agent as execute_agent_module
from flow44.ai.agents.execute.agent import ExecuteAgent
from flow44.ai.agents.execute.execution_state import ExecutionState
from flow44.ai.agents.execute.models import Task, WorkPlan
from flow44.ai.agents.plan.models import ArchitectureDesign, UXDesign
from flow44.ai.state import BuildState

from .test_optional_packages import CHART_DASHBOARD_PROMPT


class FakeSandbox:
    project_id = "project"

    def __init__(self) -> None:
        self.install_calls: list[list[str]] = []

    async def enable_optional_packages(self, package_names: list[str]) -> None:
        self.install_calls.append(package_names)


class FakeSpan:
    id = "span"

    def end(self) -> None:
        pass


class FakeLangfuse:
    def span(self, **kwargs: Any) -> FakeSpan:
        del kwargs
        return FakeSpan()


@pytest.mark.asyncio
async def test_chart_package_is_installed_before_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = FakeSandbox()
    build_state = BuildState(project_id="project", user_content=CHART_DASHBOARD_PROMPT)
    agent = ExecuteAgent("project", sandbox, build_state)  # type: ignore[arg-type]
    calls: list[str] = []

    async def fake_complete_chat(
        messages: list[Any],
        system_prompt: str,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        del messages, model, metadata
        if "## Allowed Optional Packages" in system_prompt:
            calls.append("decision")
            return '{"selected_packages":[]}'
        assert sandbox.install_calls == [["recharts"]]
        assert "`recharts` is selected" in system_prompt
        assert "comparison, trend, composition, or distribution" in system_prompt
        calls.append("merge")
        return """
        {
          "summary": "Use recharts for dashboard trends",
          "tasks": [
            {
              "id": "unsafe",
              "title": "Edit Vite",
              "description": "Change vite.config.ts",
              "files": ["vite.config.ts"],
              "depends_on": []
            },
            {
              "id": "app",
              "title": "Build app",
              "description": "Use recharts for dashboard trends",
              "files": ["src/App.tsx"],
              "depends_on": ["unsafe"]
            }
          ]
        }
        """

    monkeypatch.setattr(execute_agent_module, "complete_chat", fake_complete_chat)
    state = ExecutionState(
        build_state=build_state,
        project_id="project",
        sandbox_ref=sandbox,
        llm_metadata_fn=lambda _: {},
    )

    plan = await agent._build_technical_plan(state)

    assert calls == ["decision", "merge"]
    assert plan.selected_packages == ["recharts"]
    assert [task.files for task in plan.tasks] == [["src/App.tsx"]]
    assert plan.tasks[0].depends_on == []
    assert "recharts" in plan.tasks[0].description


@pytest.mark.asyncio
async def test_selected_packages_are_confirmed_before_codegen(monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = FakeSandbox()
    plan = WorkPlan(
        id="plan",
        summary="summary",
        architecture=ArchitectureDesign(),
        ux_design=UXDesign(),
        tasks=[Task(id="app", title="App", description="", files=["src/App.tsx"])],
        selected_packages=["mui", "recharts"],
    )
    build_state = BuildState(project_id="project", work_plan=plan)
    agent = ExecuteAgent("project", sandbox, build_state)  # type: ignore[arg-type]
    executed: list[str] = []

    async def fake_execute_task(task: Task, state: ExecutionState) -> None:
        del state
        assert sandbox.install_calls == [["@mui/material", "@emotion/react", "@emotion/styled", "recharts"]]
        executed.append(task.id)

    async def emit(event: dict[str, Any]) -> None:
        del event

    monkeypatch.setattr(agent, "_execute_task", fake_execute_task)
    state = ExecutionState(
        build_state=build_state,
        project_id="project",
        sandbox_ref=sandbox,
        emit_fn=emit,
        langfuse_client=FakeLangfuse(),
    )

    await agent._step_execute_tasks(state)

    assert executed == ["app"]
