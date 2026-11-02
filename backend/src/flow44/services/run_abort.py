import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager, suppress
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

    if not abort_listener.listening:
        _wake(project_id)


def _listen_dsn() -> str:
    return database.build_db_url(flow44.config.settings).replace("postgresql+asyncpg://", "postgresql://", 1)


class AbortListener:
    """Holds this pod's LISTEN connection for abort requests."""

    def __init__(self) -> None:
        self.listening = False
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._listen_loop())

    async def stop(self) -> None:
        # Cancelling is safe at any point: the loop only waits or pings, and the finally closes the connection.
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _listen_loop(self) -> None:
        while True:
            try:
                await self._listen_once()
            except Exception:
                logger.exception("[run-abort] LISTEN connection failed; reconnecting")
            await asyncio.sleep(_RECONNECT_DELAY)

    async def _listen_once(self) -> None:
        conn = await asyncpg.connect(_listen_dsn())
        try:
            await conn.add_listener(_CHANNEL, self._on_notify)
            self.listening = True
            while True:
                await asyncio.sleep(_PING_INTERVAL)
                await conn.fetchval("SELECT 1")  # a dead connection raises here and we reconnect
        finally:
            self.listening = False
            await conn.close()

    def _on_notify(self, _conn: Any, _pid: int, _channel: str, project_id: str) -> None:
        _wake(project_id)


abort_listener = AbortListener()
