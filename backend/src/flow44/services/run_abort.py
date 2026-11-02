"""Stopping an agent run from whichever pod receives the user's Stop.

That pod sends a Postgres NOTIFY with the project id; every pod LISTENs and wakes its own run for that project.
"""

import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import asyncpg
from sqlalchemy import text

import flow44.config
from flow44.db import database

logger = logging.getLogger(__name__)

_CHANNEL = "run_abort"
_PING_INTERVAL = 10.0
_RECONNECT_DELAY = 2.0

_watchers: dict[str, set[asyncio.Event]] = {}


@contextmanager
def watch(project_id: str) -> Iterator[asyncio.Event]:
    """An event that is set when the user aborts this project's run."""
    aborted = asyncio.Event()
    _watchers.setdefault(project_id, set()).add(aborted)
    try:
        yield aborted
    finally:
        watchers = _watchers.get(project_id, set())
        watchers.discard(aborted)
        if not watchers:
            _watchers.pop(project_id, None)


def _wake(project_id: str) -> None:
    for aborted in _watchers.get(project_id, ()):
        aborted.set()


async def request_abort(project_id: str) -> None:
    async with database.async_session() as session:
        await session.execute(
            text("SELECT pg_notify(:channel, :project_id)"), {"channel": _CHANNEL, "project_id": project_id}
        )
        await session.commit()
    # Without a LISTEN connection our own NOTIFY won't come back, so a run on this pod is woken directly.
    if not abort_listener.listening:
        _wake(project_id)


def _listen_dsn() -> str:
    return database.build_db_url(flow44.config.settings).replace("postgresql+asyncpg://", "postgresql://", 1)


class AbortListener:
    """Holds this pod's LISTEN connection for abort requests."""

    def __init__(self) -> None:
        self.listening = False
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

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
                logger.exception("[run-abort] LISTEN connection failed; reconnecting")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=_RECONNECT_DELAY)
            except TimeoutError:
                pass

    async def _listen_once(self) -> None:
        conn = await asyncpg.connect(_listen_dsn())
        try:
            await conn.add_listener(_CHANNEL, self._on_notify)
            self.listening = True
            while not self._stop.is_set():
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=_PING_INTERVAL)
                except TimeoutError:
                    await conn.fetchval("SELECT 1")  # a dead connection raises here and we reconnect
        finally:
            self.listening = False
            await conn.close()

    def _on_notify(self, _conn: Any, _pid: int, _channel: str, project_id: str) -> None:
        _wake(project_id)


abort_listener = AbortListener()
