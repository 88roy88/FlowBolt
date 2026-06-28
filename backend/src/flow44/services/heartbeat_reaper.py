import asyncio
import logging

from flow44.config import settings
from flow44.db.heartbeat import reap_stale_runs

logger = logging.getLogger(__name__)


class HeartbeatReaper:
    """Periodically closes runs whose heartbeat has gone stale.

    Replaces a per-replica boot sweep: staleness is owner-agnostic, so any replica
    safely reaps any orphaned run. The first pass runs immediately on start (it
    covers runs orphaned by this replica's own restart).
    """

    def __init__(self) -> None:
        self._interval = settings.AGENT_RUN_SWEEP_INTERVAL
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._reap_loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._stop.set()
            await self._task
            self._task = None

    async def _reap_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await reap_stale_runs()
            except Exception:
                logger.exception("[heartbeat-reaper] Sweep failed")

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
                break
            except TimeoutError:
                pass


heartbeat_reaper = HeartbeatReaper()
