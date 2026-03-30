import asyncio
import logging
import os
import shutil
import socket

from flow44.config import settings
from flow44.sandbox.base import SandboxInfo
from flow44.sandbox.main import PnpmSandbox, PnpmSandboxNamespace, PnpmSandboxUnix, PnpmSandboxWindows

logger = logging.getLogger(__name__)


class SandboxError(Exception):
    pass


class SandboxNotFoundError(SandboxError):
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

    async def create_sandbox(self, project_id: str) -> PnpmSandbox:
        async with self._lock:
            port = self._take_available_port()

        workspace_dir = os.path.join(settings.WORKSPACE_BASE_DIR, project_id)
        info = SandboxInfo(project_id=project_id, workspace_dir=workspace_dir, port=port)

        sandbox = self._create_sandbox_instance(info)
        await sandbox.start()

        self._sandboxes[project_id] = sandbox
        return sandbox

    async def destroy_sandbox(self, project_id: str, *, delete_workspace: bool = True) -> None:
        async with self._lock:
            sandbox = self._sandboxes.pop(project_id, None)

        if sandbox is None:
            return

        await sandbox.destroy(delete_workspace=delete_workspace)

        async with self._lock:
            self._available_ports.add(sandbox.port)

    def get_sandbox(self, project_id: str) -> PnpmSandbox:
        sandbox = self._sandboxes.get(project_id)
        if sandbox is None:
            raise SandboxNotFoundError(f"No sandbox found for project_id {project_id}")
        return sandbox

    async def get_or_create_sandbox(self, project_id: str) -> PnpmSandbox:
        try:
            sandbox = self.get_sandbox(project_id)
        except SandboxNotFoundError:
            sandbox = await self.create_sandbox(project_id)
        return sandbox

    @staticmethod
    async def ensure_ready(sandbox: PnpmSandbox) -> None:
        if not await sandbox.is_scaffolded():
            await sandbox.scaffold(settings.TEMPLATE_DIR)

        sandbox.configure_pnpm_store()

        if not sandbox.is_dev_server_running():
            logger.info("Starting sandbox dev server for %s", sandbox.project_id)
            await sandbox.start_dev_server()

    async def reconcile_workspaces(self, live_project_ids: set[str]) -> None:
        """Reconcile workspace state: restore live sandboxes, kill stale processes, delete orphans.

        - Kills orphan dev server processes
        - Deletes workspace directories not in live_project_ids
        - Restores sandboxes for workspaces that survived restart
        - Restarts dev servers for scaffolded sandboxes
        """
        port_start, port_end = settings.SANDBOX_PORT_RANGE_START, settings.SANDBOX_PORT_RANGE_END
        self._kill_orphan_processes(port_start, port_end)
        await self._restore_workspaces(live_project_ids)
        await self._restart_dev_servers()

    def _kill_orphan_processes(self, port_start: int, port_end: int) -> None:
        """Kill any processes occupying the sandbox port range from a previous run."""
        sandbox_cls = self._get_sandbox_class()
        for pid, port in sandbox_cls.find_pids_in_port_range(port_start, port_end):
            logger.info("Killing orphan process pid %d (port %d)", pid, port)
            sandbox_cls.kill_pid(pid)

    async def _restore_workspaces(self, live_project_ids: set[str]) -> None:
        """Scan workspace base dir, delete orphans, restore live sandboxes."""
        base = settings.WORKSPACE_BASE_DIR
        if not os.path.isdir(base):  # noqa: ASYNC240
            return

        for name in os.listdir(base):
            if name.startswith("."):
                continue
            workspace_dir = os.path.join(base, name)
            if not os.path.isdir(workspace_dir):  # noqa: ASYNC240
                continue
            if name in self._sandboxes:
                continue

            if name not in live_project_ids:
                logger.info("Removing orphan workspace %s", name)
                shutil.rmtree(workspace_dir, ignore_errors=True)
                continue

            await self._restore_one(name, workspace_dir)

    async def _restore_one(self, project_id: str, workspace_dir: str) -> None:
        """Restore a single sandbox from an existing workspace directory."""
        async with self._lock:
            if not self._available_ports:
                logger.warning("No ports left to restore sandbox %s", project_id)
                return
            try:
                port = self._take_available_port()
            except RuntimeError:
                logger.warning("No free ports to restore sandbox %s", project_id)
                return

        info = SandboxInfo(project_id=project_id, workspace_dir=workspace_dir, port=port)
        sandbox = self._create_sandbox_instance(info)
        self._sandboxes[project_id] = sandbox
        logger.info("Restored sandbox for session %s (port %d)", project_id, port)

    async def _restart_dev_servers(self) -> None:
        """Re-stamp vite configs and restart dev servers for all scaffolded sandboxes."""
        for sandbox in self._sandboxes.values():
            if await sandbox.is_scaffolded():
                sandbox._stamp_vite_config(settings.TEMPLATE_DIR)  # Re-stamp after restart
                asyncio.create_task(sandbox.start_dev_server())

    async def destroy_all(self, *, delete_workspaces: bool = False) -> None:
        project_ids = list(self._sandboxes.keys())
        for sid in project_ids:
            await self.destroy_sandbox(sid, delete_workspace=delete_workspaces)


sandbox_manager = SandboxManager()
