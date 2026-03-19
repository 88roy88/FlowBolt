from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import aiosqlite

from app.models.project import _get_db_path

logger = logging.getLogger(__name__)

# In-process notification channels (session_id → list of queues)
import asyncio

_channels: dict[str, list[asyncio.Queue]] = {}


def subscribe(session_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _channels.setdefault(session_id, []).append(queue)
    return queue


def unsubscribe(session_id: str, queue: asyncio.Queue) -> None:
    if session_id in _channels:
        try:
            _channels[session_id].remove(queue)
        except ValueError:
            pass
        if not _channels[session_id]:
            del _channels[session_id]


async def _notify(session_id: str, event: dict) -> None:
    for queue in _channels.get(session_id, []):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("[events] Queue full for session %s, dropping event", session_id)


@dataclass
class AgentEvent:
    id: int
    session_id: str
    event_type: str
    payload: dict
    created_at: str


async def init_events_table() -> None:
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS agent_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_session ON agent_events(session_id, id)
        """)
        await db.commit()


async def emit_event(session_id: str, event: dict) -> None:
    event_type = event.get("type", "unknown")
    payload_json = json.dumps(event, separators=(",", ":"))

    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            "INSERT INTO agent_events (session_id, event_type, payload) VALUES (?, ?, ?)",
            (session_id, event_type, payload_json),
        )
        await db.commit()

    await _notify(session_id, event)


async def get_events(session_id: str, after_id: int = 0) -> list[AgentEvent]:
    async with aiosqlite.connect(_get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM agent_events WHERE session_id = ? AND id > ? ORDER BY id ASC",
            (session_id, after_id),
        ) as cur:
            rows = await cur.fetchall()
            return [
                AgentEvent(
                    id=r["id"],
                    session_id=r["session_id"],
                    event_type=r["event_type"],
                    payload=json.loads(r["payload"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]


async def clear_events(session_id: str) -> None:
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute("DELETE FROM agent_events WHERE session_id = ?", (session_id,))
        await db.commit()
