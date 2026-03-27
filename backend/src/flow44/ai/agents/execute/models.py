"""Pydantic models for the execute agent: work plan, tasks, project summary."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from flow44.ai.agents.plan.models import ArchitectureDesign, UXDesign


# --- Task & WorkPlan ---


class Task(BaseModel):
    id: str
    title: str
    description: str
    files: list[str]
    depends_on: list[str] = Field(default_factory=list)
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    error: str | None = None


class WorkPlan(BaseModel):
    id: str
    summary: str
    architecture: ArchitectureDesign
    ux_design: UXDesign
    tasks: list[Task]

    def execution_layers(self) -> list[list[Task]]:
        completed_ids: set[str] = set()
        remaining = list(self.tasks)
        layers: list[list[Task]] = []

        while remaining:
            layer = [t for t in remaining if all(dep in completed_ids for dep in t.depends_on)]
            if not layer:
                layers.append(remaining)
                break
            layers.append(layer)
            completed_ids.update(t.id for t in layer)
            remaining = [t for t in remaining if t.id not in completed_ids]

        return layers


# --- Project summary ---


class ProjectSummary(BaseModel):
    summary: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    file_overview: dict[str, str] = Field(default_factory=dict)
