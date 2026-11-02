import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import asyncpg
from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Field, SQLModel, col, select

import flow44.config
from flow44.db import database

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pub/sub: Postgres NOTIFY fans events out to every pod, each pod hands them to its own sockets
# ---------------------------------------------------------------------------

_NOTIFY_CHANNEL = "flow44_events"
# NOTIFY payloads cap at 8000 bytes; ASCII-only JSON keeps characters equal to bytes.
_CHUNK_SIZE = 7000
_PING_INTERVAL = 10.0
_RECONNECT_DELAY = 2.0

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


def _deliver(project_id: str, event: dict[str, Any]) -> None:
    for queue in _channels.get(project_id, []):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("[events] Queue full for session %s, dropping event", project_id)


def _notify_payloads(project_id: str, event: dict[str, Any]) -> list[str]:
    body = json.dumps({"p": project_id, "e": event}, ensure_ascii=True)
    parts = [body[i : i + _CHUNK_SIZE] for i in range(0, len(body), _CHUNK_SIZE)]
    msg_id = uuid.uuid4().hex
    return [f"{msg_id}:{seq}:{len(parts)}:{part}" for seq, part in enumerate(parts)]


async def _publish(session: AsyncSession, project_id: str, event: dict[str, Any]) -> None:
    # One transaction, so the chunks arrive together and in order.
    for payload in _notify_payloads(project_id, event):
        await session.execute(
            text("SELECT pg_notify(:channel, :payload)"), {"channel": _NOTIFY_CHANNEL, "payload": payload}
        )


def _listen_dsn() -> str:
    return database.build_db_url(flow44.config.settings).replace("postgresql+asyncpg://", "postgresql://", 1)


class EventListener:
    """Holds this pod's LISTEN connection and hands every pod's events to the local subscribers."""

    def __init__(self) -> None:
        self.listening = False
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._partial: dict[str, list[str | None]] = {}

    def start(self) -> None:
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._listen_loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._stop.set()
            await self._task
            self._task = None

    async def _listen_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self._listen_once()
            except Exception:
                logger.exception("[events] LISTEN connection failed; reconnecting")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=_RECONNECT_DELAY)
            except TimeoutError:
                pass

    async def _listen_once(self) -> None:
        conn = await asyncpg.connect(_listen_dsn())
        try:
            await conn.add_listener(_NOTIFY_CHANNEL, self._on_notify)
            self.listening = True
            while not self._stop.is_set():
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=_PING_INTERVAL)
                except TimeoutError:
                    await conn.fetchval("SELECT 1")  # a dead connection raises here and we reconnect
        finally:
            self.listening = False
            # Chunks of a message cut off by the drop will never complete.
            self._partial.clear()
            await conn.close()

    def _on_notify(self, _conn: Any, _pid: int, _channel: str, payload: str) -> None:
        try:
            msg_id, seq, total, part = payload.split(":", 3)
            if total == "1":
                body = part
            else:
                parts = self._partial.setdefault(msg_id, [None] * int(total))
                parts[int(seq)] = part
                if None in parts:
                    return
                del self._partial[msg_id]
                body = "".join(p for p in parts if p is not None)
            message = json.loads(body)
            _deliver(message["p"], message["e"])
        except Exception:
            logger.exception("[events] Dropping a malformed notification")


event_listener = EventListener()


def _deliver_unless_listening(project_id: str, event: dict[str, Any]) -> None:
    # Without a LISTEN connection our own NOTIFY won't come back, so hand the event over directly.
    if not event_listener.listening:
        _deliver(project_id, event)


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
    event.setdefault("_ts", datetime.now(UTC).isoformat())

    async with database.async_session() as session:
        row = AgentEvent(project_id=project_id, event_type=event.get("type", "unknown"), payload=event)
        session.add(row)
        if notify:
            await _publish(session, project_id, event)
        await session.commit()

    if notify:
        _deliver_unless_listening(project_id, event)


async def emit_transient(project_id: str, event: dict[str, Any]) -> None:
    # Live-only: never stored, so a history reload won't replay it.
    try:
        async with database.async_session() as session:
            await _publish(session, project_id, event)
            await session.commit()
    except Exception:
        # Losing the other pods' copy beats failing the caller; this pod still gets it below.
        logger.warning("[events] Publishing a transient event failed for session %s", project_id, exc_info=True)
        _deliver(project_id, event)
        return
    _deliver_unless_listening(project_id, event)


async def get_events(project_id: str, after_id: int = 0) -> list[AgentEvent]:
    async with database.async_session() as session:
        result = await session.execute(
            select(AgentEvent)
            .where(AgentEvent.project_id == project_id, AgentEvent.id > after_id)  # type: ignore[operator]
            .order_by(AgentEvent.id.asc())  # type: ignore[union-attr]
        )
        return list(result.scalars().all())


async def get_latest_event(project_id: str, event_type: str) -> AgentEvent | None:
    async with database.async_session() as session:
        result = await session.execute(
            select(AgentEvent)
            .where(AgentEvent.project_id == project_id, AgentEvent.event_type == event_type)
            .order_by(AgentEvent.id.desc())  # type: ignore[union-attr]
            .limit(1)
        )
        return result.scalars().first()


async def clear_events(project_id: str) -> None:
    async with database.async_session() as session:
        await session.execute(delete(AgentEvent).where(col(AgentEvent.project_id) == project_id))
        await session.commit()


async def get_versions(project_id: str) -> list[AgentEvent]:
    async with database.async_session() as session:
        result = await session.execute(
            select(AgentEvent)
            .where(AgentEvent.project_id == project_id, AgentEvent.event_type == "version_committed")
            .order_by(AgentEvent.id.asc())  # type: ignore[union-attr]
        )
        return list(result.scalars().all())


async def trim_events_after(project_id: str, event_id: int) -> None:
    async with database.async_session() as session:
        await session.execute(
            delete(AgentEvent).where(col(AgentEvent.project_id) == project_id, col(AgentEvent.id) > event_id)
        )
        await session.commit()
