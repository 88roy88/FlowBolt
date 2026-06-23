import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, delete, func
from sqlmodel import Field, SQLModel, col, select

from flow44.db import database

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory pub/sub (not DB-related)
# ---------------------------------------------------------------------------

_channels: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}


def subscribe(project_id: str) -> asyncio.Queue[dict[str, Any]]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    _channels.setdefault(project_id, []).append(queue)
    return queue


def unsubscribe(project_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
    if project_id in _channels:
        try:
            _channels[project_id].remove(queue)
        except ValueError:
            pass
        if not _channels[project_id]:
            del _channels[project_id]


async def _notify(project_id: str, event: dict[str, Any]) -> None:
    for queue in _channels.get(project_id, []):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("[events] Queue full for session %s, dropping event", project_id)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class AgentEvent(SQLModel, table=True):
    __tablename__ = "agent_events"

    id: int | None = Field(default=None, primary_key=True)
    project_id: str = Field(
        sa_column=Column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    )
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, default={}))
    created_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def emit_event(project_id: str, event: dict[str, Any], *, notify: bool = True) -> None:
    async with database.async_session() as session:
        row = AgentEvent(
            project_id=project_id,
            event_type=event.get("type", "unknown"),
            payload=event,
            created_at=datetime.now(UTC),
        )
        session.add(row)
        await session.commit()

    if notify:
        await _notify(project_id, event)


async def emit_transient(project_id: str, event: dict[str, Any]) -> None:
    # Broadcast only — never persisted, so not replayed on history reload.
    await _notify(project_id, event)


async def get_events(project_id: str, after_id: int = 0) -> list[AgentEvent]:
    async with database.async_session() as session:
        result = await session.execute(
            select(AgentEvent)
            .where(AgentEvent.project_id == project_id, AgentEvent.id > after_id)  # type: ignore[operator]
            .order_by(AgentEvent.id.asc())  # type: ignore[union-attr]
        )
        return list(result.scalars().all())


async def clear_events(project_id: str) -> None:
    async with database.async_session() as session:
        await session.execute(delete(AgentEvent).where(col(AgentEvent.project_id) == project_id))
        await session.commit()


async def get_versions(project_id: str) -> list[AgentEvent]:
    """Return the project's version_committed events (the app version history)."""
    async with database.async_session() as session:
        result = await session.execute(
            select(AgentEvent)
            .where(AgentEvent.project_id == project_id, AgentEvent.event_type == "version_committed")
            .order_by(AgentEvent.id.asc())  # type: ignore[union-attr]
        )
        return list(result.scalars().all())


async def trim_events_after(project_id: str, event_id: int) -> None:
    """Delete all events newer than event_id (used when a restore forks history)."""
    async with database.async_session() as session:
        await session.execute(
            delete(AgentEvent).where(col(AgentEvent.project_id) == project_id, col(AgentEvent.id) > event_id)
        )
        await session.commit()
