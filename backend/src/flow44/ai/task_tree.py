from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flow44.ai.schemas import ArchitectureDesign, UXDesign


# TODO: why dataclass instead of pydantic?
@dataclass
class Task:
    id: str
    title: str
    description: str
    files: list[str]
    depends_on: list[str] = field(default_factory=list)
    # TODO: use literal
    status: str = "pending"  # pending | running | completed | failed
    error: str | None = None


# TODO: why is this even dataclass?
# TODO: is there a more elegant way to do this? also, move to utils
@dataclass
class WorkPlan:
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
