from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flow44.ai.agents._base import BaseAgent

_running: dict[str, BaseAgent] = {}


def register(session_id: str, agent: BaseAgent) -> None:
    _running[session_id] = agent


def get(session_id: str) -> BaseAgent | None:
    return _running.get(session_id)


def remove(session_id: str) -> None:
    _running.pop(session_id, None)


# TODO: not sure im a fan of this global mutable state or the registry pattern in general.
