"""Tests for WorkPlan dependency resolution."""

from __future__ import annotations

from flow44.ai.agents.plan.models import ArchitectureDesign, UXDesign
from flow44.ai.agents.execute.models import Task, WorkPlan


def _make_plan(tasks: list[Task]) -> WorkPlan:
    return WorkPlan(
        id="test",
        summary="test plan",
        architecture=ArchitectureDesign(),
        ux_design=UXDesign(),
        tasks=tasks,
    )


class TestExecutionLayers:
    def test_no_dependencies(self) -> None:
        """All tasks with no deps should run in a single layer."""
        plan = _make_plan(
            [
                Task(id="t1", title="A", description="", files=[]),
                Task(id="t2", title="B", description="", files=[]),
                Task(id="t3", title="C", description="", files=[]),
            ]
        )

        layers = plan.execution_layers()
        assert len(layers) == 1
        assert len(layers[0]) == 3

    def test_linear_chain(self) -> None:
        """A → B → C should produce 3 layers of 1 task each."""
        plan = _make_plan(
            [
                Task(id="t1", title="A", description="", files=[]),
                Task(id="t2", title="B", description="", files=[], depends_on=["t1"]),
                Task(id="t3", title="C", description="", files=[], depends_on=["t2"]),
            ]
        )

        layers = plan.execution_layers()
        assert len(layers) == 3
        assert layers[0][0].id == "t1"
        assert layers[1][0].id == "t2"
        assert layers[2][0].id == "t3"

    def test_diamond_dependency(self) -> None:
        """Diamond: A → (B, C) → D. B and C should be in the same layer."""
        plan = _make_plan(
            [
                Task(id="t1", title="A", description="", files=[]),
                Task(id="t2", title="B", description="", files=[], depends_on=["t1"]),
                Task(id="t3", title="C", description="", files=[], depends_on=["t1"]),
                Task(id="t4", title="D", description="", files=[], depends_on=["t2", "t3"]),
            ]
        )

        layers = plan.execution_layers()
        assert len(layers) == 3
        assert layers[0][0].id == "t1"
        layer2_ids = {t.id for t in layers[1]}
        assert layer2_ids == {"t2", "t3"}
        assert layers[2][0].id == "t4"

    def test_circular_dependency_fallback(self) -> None:
        """Circular deps should not infinite loop — remaining tasks dumped in last layer."""
        plan = _make_plan(
            [
                Task(id="t1", title="A", description="", files=[], depends_on=["t2"]),
                Task(id="t2", title="B", description="", files=[], depends_on=["t1"]),
            ]
        )

        layers = plan.execution_layers()
        # Both tasks end up in a single fallback layer
        assert len(layers) == 1
        assert len(layers[0]) == 2

    def test_empty_plan(self) -> None:
        plan = _make_plan([])
        layers = plan.execution_layers()
        assert layers == []

    def test_single_task(self) -> None:
        plan = _make_plan(
            [
                Task(id="t1", title="A", description="", files=["src/App.tsx"]),
            ]
        )

        layers = plan.execution_layers()
        assert len(layers) == 1
        assert layers[0][0].files == ["src/App.tsx"]

    def test_typical_project_structure(self) -> None:
        """Realistic: types → hooks + components → App integration."""
        plan = _make_plan(
            [
                Task(id="types", title="Types", description="", files=["src/types.ts"]),
                Task(id="hooks", title="Hooks", description="", files=["src/hooks.ts"], depends_on=["types"]),
                Task(id="header", title="Header", description="", files=["src/Header.tsx"], depends_on=["types"]),
                Task(id="sidebar", title="Sidebar", description="", files=["src/Sidebar.tsx"], depends_on=["types"]),
                Task(
                    id="app",
                    title="App",
                    description="",
                    files=["src/App.tsx"],
                    depends_on=["hooks", "header", "sidebar"],
                ),
            ]
        )

        layers = plan.execution_layers()
        assert len(layers) == 3
        assert layers[0][0].id == "types"
        layer2_ids = {t.id for t in layers[1]}
        assert layer2_ids == {"hooks", "header", "sidebar"}
        assert layers[2][0].id == "app"
