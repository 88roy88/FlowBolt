from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flow44.ai.agents._base import BaseAgent

_running: dict[str, BaseAgent] = {}


def register(project_id: str, agent: BaseAgent) -> None:
    _running[project_id] = agent


def get(project_id: str) -> BaseAgent | None:
    return _running.get(project_id)


def remove(project_id: str) -> None:
    _running.pop(project_id, None)


# TODO: not sure im a fan of this global mutable state or the registry pattern in general.
