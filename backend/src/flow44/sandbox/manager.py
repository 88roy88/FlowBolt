import asyncio
import glob
import logging
import os
import shutil
import socket

from flow44.config import settings
from flow44.sandbox.base import BACKGROUND_PIDFILE_SUFFIX, SandboxInfo, workspace_path
from flow44.sandbox.idle_reaper import idle_reaper
from flow44.sandbox.main import PnpmSandbox, PnpmSandboxNamespace, PnpmSandboxUnix, PnpmSandboxWindows

logger = logging.getLogger(__name__)


def _cmdline_references(cmdline: str | None, path: str) -> bool:
    """Whether a process command line mentions `path` (or its resolved form)."""
    if not cmdline:
        return False
    haystack = os.path.normcase(cmdline)
    return any(os.path.normcase(p) in haystack for p in {path, os.path.abspath(path), os.path.realpath(path)})


class SandboxError(Exception):
    pass


class SandboxManager:
    def __init__(self) -> None:
        self._sandboxes: dict[str, PnpmSandbox] = {}
        self._available_ports: set[int] = set(
            range(settings.SANDBOX_PORT_RANGE_START, settings.SANDBOX_PORT_RANGE_END + 1)
        )
        self._lock = asyncio.Lock()

    @staticmethod
    def _port_is_available(port: int) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False
        finally:
            sock.close()

    def _take_available_port(self) -> int:
        for port in sorted(self._available_ports):
            if not self._port_is_available(port):
                continue
            self._available_ports.remove(port)
            return port
        raise RuntimeError("No available ports in the sandbox pool")

    @staticmethod
    def _get_sandbox_class() -> type[PnpmSandbox]:
        if settings.SANDBOX_MODE == "namespaced":
            return PnpmSandboxNamespace
        if os.name == "nt":
            return PnpmSandboxWindows
        return PnpmSandboxUnix

    def _create_sandbox_instance(self, info: SandboxInfo) -> PnpmSandbox:
        return self._get_sandbox_class()(info)

    async def get_sandbox(self, project_id: str) -> PnpmSandbox:
        """Get an active sandbox, or re-activate it if it was suspended."""
        sandbox = self._sandboxes.get(project_id)
        if sandbox is None:
            async with self._lock:
                port = self._take_available_port()

            workspace_dir = workspace_path(project_id)
            info = SandboxInfo(project_id=project_id, workspace_dir=workspace_dir, port=port)

            sandbox = self._create_sandbox_instance(info)
            await sandbox.start()

            self._sandboxes[project_id] = sandbox

        idle_reaper.touch(project_id)
        return sandbox

    async def wake_sandbox(self, project_id: str) -> PnpmSandbox:
        """Wake a suspended sandbox: get it and start the dev server (non-blocking)."""
        sandbox = await self.get_sandbox(project_id)
        await self.start_dev_server(sandbox)
        return sandbox

    async def create_sandbox(self, project_id: str) -> PnpmSandbox:
        """Create a brand-new sandbox: get, scaffold, and start the dev server."""
        sandbox = await self.get_sandbox(project_id)
        await sandbox.scaffold(settings.TEMPLATE_DIR)
        await self.start_dev_server(sandbox)
        return sandbox

    async def suspend_sandbox(self, project_id: str) -> None:
        """Suspend a sandbox: kill processes and free port, but keep workspace on disk."""
        async with self._lock:
            sandbox = self._sandboxes.pop(project_id, None)

        if sandbox is None:
            return

        await sandbox.destroy(delete_workspace=False)

        async with self._lock:
            self._available_ports.add(sandbox.port)

    async def destroy_sandbox(self, project_id: str) -> None:
        """Permanently destroy a sandbox and delete its workspace from disk.

        Best-effort: failures are logged and swallowed. Any orphaned workspace left
        behind is cleaned up later by reconcile_workspaces().
        """
        try:
            await self.suspend_sandbox(project_id)
            workspace_dir = workspace_path(project_id)
            await asyncio.to_thread(shutil.rmtree, workspace_dir, ignore_errors=True)
        except Exception:
            logger.exception("Failed to destroy sandbox %s", project_id)

    @staticmethod
    async def start_dev_server(sandbox: PnpmSandbox) -> None:
        """Start the dev server if it's not already running."""
        if not sandbox.is_dev_server_running():
            logger.info("Starting sandbox dev server for %s", sandbox.project_id)
            await sandbox.start_dev_server()

    async def reconcile_workspaces(self, live_project_ids: set[str]) -> None:
        """Reconcile workspace state: kill stale processes and delete orphan directories.

        Sandbox objects and ports are NOT pre-allocated — they are created lazily
        via wake_sandbox() when a user first connects.
        """
        os.makedirs(settings.WORKSPACE_BASE_DIR, exist_ok=True)
        os.makedirs(settings.PNPM_STORE_DIR, exist_ok=True)

        port_start, port_end = settings.SANDBOX_PORT_RANGE_START, settings.SANDBOX_PORT_RANGE_END
        self._kill_orphan_processes(port_start, port_end)
        self._delete_orphan_workspaces(live_project_ids)

    def _kill_orphan_processes(self, port_start: int, port_end: int) -> None:
        """Kill sandbox processes left behind by a previous run.

        Only processes provably started by this backend are killed: other software
        commonly listens in the sandbox port range (e.g. Docker Desktop's port proxy),
        and killing it can take down the whole host service.
        """
        sandbox_cls = self._get_sandbox_class()
        base = settings.WORKSPACE_BASE_DIR

        # Pass 1: background processes recorded in pidfiles. The cmdline check guards
        # against the PID having been reused by an unrelated process since.
        for pidfile in glob.glob(os.path.join(glob.escape(base), "*", f".*{BACKGROUND_PIDFILE_SUFFIX}")):
            workspace_dir = os.path.dirname(pidfile)
            try:
                with open(pidfile, encoding="utf-8") as f:
                    pid = int(f.read().strip())
            except (OSError, ValueError):
                pid = None
            if pid is not None and _cmdline_references(sandbox_cls.get_pid_cmdline(pid), workspace_dir):
                logger.info("Killing orphan sandbox process pid %d (%s)", pid, pidfile)
                sandbox_cls.kill_pid(pid)
            try:
                os.remove(pidfile)
            except OSError:
                pass

        # Pass 2: listeners in the port range whose parent is gone (or that predate
        # pidfiles). Kill only those running out of a workspace; leave the rest alone.
        for pid, port in sandbox_cls.find_pids_in_port_range(port_start, port_end):
            if _cmdline_references(sandbox_cls.get_pid_cmdline(pid), base):
                logger.info("Killing orphan sandbox process pid %d (port %d)", pid, port)
                sandbox_cls.kill_pid(pid)
            else:
                logger.warning(
                    "Port %d in the sandbox range is held by a non-sandbox process (pid %d); leaving it alone",
                    port,
                    pid,
                )

    def _delete_orphan_workspaces(self, live_project_ids: set[str]) -> None:
        """Delete workspace directories for projects no longer in the database."""
        base = settings.WORKSPACE_BASE_DIR
        if not os.path.isdir(base):
            return

        for name in os.listdir(base):
            if name.startswith("."):
                continue
            workspace_dir = os.path.join(base, name)
            if not os.path.isdir(workspace_dir):
                continue
            if name not in live_project_ids:
                logger.info("Removing orphan workspace %s", name)
                shutil.rmtree(workspace_dir, ignore_errors=True)

    def has_active_sandbox(self, project_id: str) -> bool:
        return project_id in self._sandboxes

    def active_project_ids(self) -> list[str]:
        return list(self._sandboxes.keys())

    async def suspend_all(self) -> None:
        """Suspend all active sandboxes (used during shutdown)."""
        project_ids = list(self._sandboxes.keys())
        for sid in project_ids:
            await self.suspend_sandbox(sid)


sandbox_manager = SandboxManager()
