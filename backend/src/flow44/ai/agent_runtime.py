"""In-process tracking of background agent tasks per project."""

from __future__ import annotations

_active_counts: dict[str, int] = {}


def mark_agent_started(project_id: str) -> None:
    _active_counts[project_id] = _active_counts.get(project_id, 0) + 1


def mark_agent_finished(project_id: str) -> None:
    count = _active_counts.get(project_id, 0)
    if count <= 1:
        _active_counts.pop(project_id, None)
    else:
        _active_counts[project_id] = count - 1


def is_agent_active(project_id: str) -> bool:
    return _active_counts.get(project_id, 0) > 0


def reset_agent_runtime() -> None:
    """Clear all counters (for tests)."""
    _active_counts.clear()
