"""In-memory project registry tracking active sandbox sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from flow44.sandbox.base import SandboxInfo


@dataclass
class ProjectSession:
    """Metadata for an active project session."""

    project_id: str
    sandbox_info: SandboxInfo
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ProjectRegistry:
    """Simple in-memory dict mapping project_id -> ProjectSession."""

    def __init__(self) -> None:
        self._sessions: dict[str, ProjectSession] = {}

    def register(self, project_id: str, sandbox_info: SandboxInfo) -> ProjectSession:
        info = ProjectSession(project_id=project_id, sandbox_info=sandbox_info)
        self._sessions[project_id] = info
        return info

    def get(self, project_id: str) -> ProjectSession | None:
        return self._sessions.get(project_id)

    def remove(self, project_id: str) -> None:
        self._sessions.pop(project_id, None)

    def all(self) -> list[ProjectSession]:
        return list(self._sessions.values())


# Module-level singleton
project_registry = ProjectRegistry()
