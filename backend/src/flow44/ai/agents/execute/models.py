"""Pydantic models for ExecuteAgent: tasks, work plan, and project summary."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from flow44.ai.agents.plan.models import ArchitectureDesign, UXDesign


class Task(BaseModel):
    """A single task in the work plan."""

    id: str
    title: str
    description: str
    files: list[str]
    depends_on: list[str] = Field(default_factory=list)
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    error: str | None = None


class WorkPlan(BaseModel):
    """Complete work plan with tasks and execution order."""

    id: str
    summary: str
    architecture: ArchitectureDesign
    ux_design: UXDesign
    tasks: list[Task]
    uses_routing: bool = False

    def execution_layers(self) -> list[list[Task]]:
        """Return tasks grouped by dependency layers for parallel execution."""
        completed_ids: set[str] = set()
        remaining = list(self.tasks)
        layers: list[list[Task]] = []

        while remaining:
            # Find tasks whose dependencies are all completed
            layer = [t for t in remaining if all(dep in completed_ids for dep in t.depends_on)]
            if not layer:
                # Circular dependency or error - just add all remaining
                layers.append(remaining)
                break
            layers.append(layer)
            completed_ids.update(t.id for t in layer)
            remaining = [t for t in remaining if t.id not in completed_ids]

        return layers


class ProjectSummary(BaseModel):
    """Project summary generated after execution."""

    summary: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    file_overview: dict[str, str] = Field(default_factory=dict)
