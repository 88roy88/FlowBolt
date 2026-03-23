import asyncio
import logging
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel, select

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
    project_id: str = Field(index=True)
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, default={}))
    created_at: str | None = Field(default=None)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def emit_event(project_id: str, event: dict[str, Any], *, notify: bool = True) -> None:
    event_type = event.get("type", "unknown")

    async with database.async_session() as session:
        row = AgentEvent(project_id=project_id, event_type=event_type, payload=event)
        session.add(row)
        await session.commit()

    if notify:
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
        result = await session.execute(select(AgentEvent).where(AgentEvent.project_id == project_id))
        for row in result.scalars().all():
            await session.delete(row)
        await session.commit()
