import asyncio
import logging
import time

from flow44.config import settings

logger = logging.getLogger(__name__)


class IdleReaper:
    """Tracks last-activity timestamps per project and periodically evicts idle sandboxes.

    Evicted sandboxes are destroyed (processes killed, port freed) but the workspace
    directory is preserved so re-creation on reconnect is fast (no re-scaffold needed).
    """

    def __init__(self) -> None:
        self._ttl = settings.SANDBOX_IDLE_TTL_SECONDS
        self._check_interval = settings.SANDBOX_IDLE_CHECK_INTERVAL_SECONDS
        self._last_activity: dict[str, float] = {}
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def touch(self, project_id: str) -> None:
        self._last_activity[project_id] = time.monotonic()

    def remove(self, project_id: str) -> None:
        self._last_activity.pop(project_id, None)

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
        from flow44.sandbox.manager import sandbox_manager  # noqa: PLC0415

        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._check_interval)
                break
            except TimeoutError:
                pass

            now = time.monotonic()
            to_evict: list[str] = []

            for project_id, last_ts in list(self._last_activity.items()):
                if now - last_ts > self._ttl:
                    to_evict.append(project_id)

            for project_id in to_evict:
                if project_id not in sandbox_manager._sandboxes:
                    self._last_activity.pop(project_id, None)
                    continue

                idle_seconds = now - self._last_activity.get(project_id, now)
                logger.info(
                    "[idle-reaper] Evicting idle sandbox for project %s (idle %.0fs)",
                    project_id,
                    idle_seconds,
                )
                await sandbox_manager.suspend_sandbox(project_id)
                self._last_activity.pop(project_id, None)


idle_reaper = IdleReaper()
