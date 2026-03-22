from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import aiosqlite

from flow44.models.project import _get_db_path

logger = logging.getLogger(__name__)

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


@dataclass
class AgentEvent:
    id: int
    project_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: str


async def init_events_table() -> None:
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS agent_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_project ON agent_events(project_id, id)
        """)
        await db.commit()

    # Migration: rename session_id → project_id in existing DBs
    async with aiosqlite.connect(_get_db_path()) as db:
        try:
            await db.execute("ALTER TABLE agent_events RENAME COLUMN session_id TO project_id")
            await db.commit()
        except Exception:  # noqa: S110 — column already named project_id or doesn't exist
            pass


async def emit_event(project_id: str, event: dict[str, Any], *, notify: bool = True) -> None:
    event_type = event.get("type", "unknown")
    payload_json = json.dumps(event, separators=(",", ":"))

    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            "INSERT INTO agent_events (project_id, event_type, payload) VALUES (?, ?, ?)",
            (project_id, event_type, payload_json),
        )
        await db.commit()

    if notify:
        await _notify(project_id, event)


async def get_events(project_id: str, after_id: int = 0) -> list[AgentEvent]:
    async with aiosqlite.connect(_get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM agent_events WHERE project_id = ? AND id > ? ORDER BY id ASC",
            (project_id, after_id),
        ) as cur:
            rows = await cur.fetchall()
            return [
                AgentEvent(
                    id=r["id"],
                    project_id=r["project_id"],
                    event_type=r["event_type"],
                    payload=json.loads(r["payload"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]


async def clear_events(project_id: str) -> None:
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute("DELETE FROM agent_events WHERE project_id = ?", (project_id,))
        await db.commit()
