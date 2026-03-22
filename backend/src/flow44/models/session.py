"""In-memory session registry tracking active sandbox sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from flow44.sandbox.base import SandboxInfo


@dataclass
class SessionInfo:
    """Metadata for an active session."""

    session_id: str
    project_id: str
    sandbox_info: SandboxInfo
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SessionRegistry:
    """Simple in-memory dict mapping session_id -> SessionInfo."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionInfo] = {}

    def register(self, session_id: str, project_id: str, sandbox_info: SandboxInfo) -> SessionInfo:
        info = SessionInfo(
            session_id=session_id,
            project_id=project_id,
            sandbox_info=sandbox_info,
        )
        self._sessions[session_id] = info
        return info

    def get(self, session_id: str) -> SessionInfo | None:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def all(self) -> list[SessionInfo]:
        return list(self._sessions.values())


# Module-level singleton
session_registry = SessionRegistry()
