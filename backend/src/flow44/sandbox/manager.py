import asyncio
import logging
import os
import shutil
import socket

from flow44.config import settings
from flow44.sandbox.base import SandboxInfo
from flow44.sandbox.idle_reaper import idle_reaper
from flow44.sandbox.main import PnpmSandbox, PnpmSandboxNamespace, PnpmSandboxUnix, PnpmSandboxWindows

logger = logging.getLogger(__name__)


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

            workspace_dir = os.path.join(settings.WORKSPACE_BASE_DIR, project_id)
            info = SandboxInfo(project_id=project_id, workspace_dir=workspace_dir, port=port)

            sandbox = self._create_sandbox_instance(info)
            await sandbox.start()

            self._sandboxes[project_id] = sandbox

        idle_reaper.touch(project_id)
        return sandbox

    async def wake_sandbox(self, project_id: str) -> PnpmSandbox:
        """Wake a suspended sandbox: get it and start the dev server."""
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
        """Permanently destroy a sandbox and delete its workspace from disk."""
        await self.suspend_sandbox(project_id)
        workspace_dir = os.path.join(settings.WORKSPACE_BASE_DIR, project_id)
        if os.path.isdir(workspace_dir):
            shutil.rmtree(workspace_dir, ignore_errors=True)


    @staticmethod
    async def start_dev_server(sandbox: PnpmSandbox) -> None:
        """Start the dev server if it's not already running."""
        sandbox.configure_npmrc()
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
        """Kill any processes occupying the sandbox port range from a previous run."""
        sandbox_cls = self._get_sandbox_class()
        for pid, port in sandbox_cls.find_pids_in_port_range(port_start, port_end):
            logger.info("Killing orphan process pid %d (port %d)", pid, port)
            sandbox_cls.kill_pid(pid)

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

    async def suspend_all(self) -> None:
        """Suspend all active sandboxes (used during shutdown)."""
        project_ids = list(self._sandboxes.keys())
        for sid in project_ids:
            await self.suspend_sandbox(sid)


sandbox_manager = SandboxManager()
