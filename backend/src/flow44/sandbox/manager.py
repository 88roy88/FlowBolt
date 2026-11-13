import asyncio
import logging
import os
import shutil
import socket
import time

from flow44.config import settings
from flow44.db.events import emit_event
from flow44.db.locks import LockNamespace, LockTimeout, advisory_lock
from flow44.sandbox.base import SandboxInfo, workspace_path
from flow44.sandbox.idle_reaper import idle_reaper
from flow44.sandbox.main import PnpmSandbox, PnpmSandboxNamespace, PnpmSandboxUnix, PnpmSandboxWindows
from flow44.services.versioning import service as versioning

logger = logging.getLogger(__name__)

# Don't delete orphan workspaces that may not have finished initializing.
_ORPHAN_MIN_AGE_SECONDS = 10 * 60


class SandboxError(Exception):
    pass


class SandboxManager:
    def __init__(self) -> None:
        self._sandboxes: dict[str, PnpmSandbox] = {}
        self._available_ports: set[int] = set(
            range(settings.SANDBOX_PORT_RANGE_START, settings.SANDBOX_PORT_RANGE_END + 1)
        )
        self._lock = asyncio.Lock()
        self._setup_tasks: dict[str, asyncio.Task[None]] = {}

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
        """Get the sandbox and start its dev server (non-blocking).

        On a project's first wake, set up its workspace first (docs/multi-pod.md, "Workspaces are set up on first use").
        """
        sandbox = await self.get_sandbox(project_id)
        if project_id in self._setup_tasks:
            return sandbox
        if not await sandbox.is_scaffolded():
            task = asyncio.create_task(self._set_up_workspace(sandbox))
            self._setup_tasks[project_id] = task
            task.add_done_callback(lambda _: self._setup_tasks.pop(project_id, None))
            return sandbox
        await self.start_dev_server(sandbox)
        return sandbox

    async def _set_up_workspace(self, sandbox: PnpmSandbox) -> None:
        project_id = sandbox.project_id
        try:
            # Lock because another pod may be setting up the same workspace.
            async with advisory_lock(LockNamespace.workspace, project_id):
                if not await sandbox.is_scaffolded():
                    await sandbox.scaffold(settings.TEMPLATE_DIR)
            await versioning.ensure_repo(project_id)
            await self.start_dev_server(sandbox)
        except LockTimeout:
            logger.info("[sandbox] Workspace setup for %s is running elsewhere; retrying on next wake", project_id)
        except Exception:
            logger.exception("[sandbox] Workspace setup failed for project %s", project_id)
            await emit_event(project_id, {"type": "error", "message": "Project setup failed"})

    async def suspend_sandbox(self, project_id: str) -> None:
        """Suspend a sandbox: kill processes and free port, but keep workspace on disk."""
        setup = self._setup_tasks.pop(project_id, None)
        if setup is not None:
            setup.cancel()

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

        min_mtime = time.time() - _ORPHAN_MIN_AGE_SECONDS
        for name in os.listdir(base):
            if name.startswith("."):
                continue
            workspace_dir = os.path.join(base, name)
            if not os.path.isdir(workspace_dir):
                continue
            if name not in live_project_ids and os.path.getmtime(workspace_dir) < min_mtime:
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
