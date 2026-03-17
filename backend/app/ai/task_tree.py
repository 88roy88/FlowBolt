"""Data structures for the multi-phase agent work plan."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Task:
    id: str
    title: str
    description: str
    files: list[str]
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"  # pending | running | completed | failed
    error: str | None = None


@dataclass
class WorkPlan:
    id: str
    summary: str
    architecture: dict
    ux_design: dict
    tasks: list[Task]

    def execution_layers(self) -> list[list[Task]]:
        """Group tasks into dependency layers for parallel execution.

        Tasks in the same layer have all dependencies satisfied by prior layers.
        """
        completed_ids: set[str] = set()
        remaining = list(self.tasks)
        layers: list[list[Task]] = []

        while remaining:
            layer = [
                t for t in remaining
                if all(dep in completed_ids for dep in t.depends_on)
            ]
            if not layer:
                # Circular dependency or unresolvable — just run everything left
                layers.append(remaining)
                break
            layers.append(layer)
            completed_ids.update(t.id for t in layer)
            remaining = [t for t in remaining if t.id not in completed_ids]

        return layers
