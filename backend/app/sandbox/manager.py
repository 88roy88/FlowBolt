from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal

from app.config import settings
from app.sandbox.base import Sandbox, SandboxInfo

logger = logging.getLogger(__name__)


def stamp_vite_config(session_id: str, workspace_dir: str) -> None:
    """Replace the ``{{SESSION_ID}}`` placeholder in the template's vite.config.ts."""
    path = os.path.join(workspace_dir, "vite.config.ts")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.replace("{{SESSION_ID}}", session_id))


class SandboxManager:

    def __init__(self) -> None:
        self._sandboxes: dict[str, Sandbox] = {}
        self._available_ports: set[int] = set(
            range(settings.SANDBOX_PORT_RANGE_START, settings.SANDBOX_PORT_RANGE_END + 1)
        )
        self._lock = asyncio.Lock()

    def _create_sandbox_instance(self, info: SandboxInfo) -> Sandbox:
        if settings.SANDBOX_MODE == "namespaced":
            from app.sandbox.namespaced import NamespacedSandbox
            return NamespacedSandbox(info)
        else:
            from app.sandbox.local import LocalSandbox
            return LocalSandbox(info)

    async def create_sandbox(self, session_id: str) -> Sandbox:
        async with self._lock:
            if session_id in self._sandboxes:
                return self._sandboxes[session_id]

            if not self._available_ports:
                raise RuntimeError("No available ports in the sandbox pool")

            port = self._available_ports.pop()

        workspace_dir = os.path.join(settings.WORKSPACE_BASE_DIR, session_id)
        info = SandboxInfo(session_id=session_id, workspace_dir=workspace_dir, port=port)

        sandbox = self._create_sandbox_instance(info)
        await sandbox.start()

        self._sandboxes[session_id] = sandbox
        return sandbox

    async def destroy_sandbox(self, session_id: str, *, delete_workspace: bool = True) -> None:
        async with self._lock:
            sandbox = self._sandboxes.pop(session_id, None)

        if sandbox is None:
            return

        await sandbox.destroy(delete_workspace=delete_workspace)

        async with self._lock:
            self._available_ports.add(sandbox.port)

    def get_sandbox(self, session_id: str) -> Sandbox | None:
        return self._sandboxes.get(session_id)

    @staticmethod
    def _kill_stale_dev_servers() -> None:
        """Find orphan pnpm dev processes in our port range and kill them."""
        import subprocess as _sp

        port_start = settings.SANDBOX_PORT_RANGE_START
        port_end = settings.SANDBOX_PORT_RANGE_END
        try:
            result = _sp.run(
                ["pgrep", "-f", "pnpm dev --port"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return
            for pid_str in result.stdout.strip().splitlines():
                pid = int(pid_str.strip())
                try:
                    cmdline = _sp.run(
                        ["ps", "-p", str(pid), "-o", "args="],
                        capture_output=True, text=True, timeout=5,
                    ).stdout.strip()
                except Exception:
                    continue
                for part in cmdline.split():
                    try:
                        port = int(part)
                        if port_start <= port <= port_end:
                            try:
                                os.killpg(os.getpgid(pid), signal.SIGTERM)
                            except (ProcessLookupError, PermissionError, OSError):
                                try:
                                    os.kill(pid, signal.SIGTERM)
                                except (ProcessLookupError, PermissionError):
                                    pass
                            logger.info("Killed stale dev server pid %d (port %d)", pid, port)
                            break
                    except ValueError:
                        continue
        except FileNotFoundError:
            pass
        except Exception:
            logger.debug("Failed to clean stale dev servers", exc_info=True)

    async def restore_existing_workspaces(self, live_session_ids: set[str]) -> None:
        """Re-register sandboxes for workspaces that survived a restart.

        Orphan directories (not in live_session_ids) are deleted.
        """
        self._kill_stale_dev_servers()

        base = settings.WORKSPACE_BASE_DIR
        if not os.path.isdir(base):
            return

        for name in os.listdir(base):
            workspace_dir = os.path.join(base, name)
            if not os.path.isdir(workspace_dir):
                continue
            if name in self._sandboxes:
                continue

            if name not in live_session_ids:
                logger.info("Removing orphan workspace %s", name)
                shutil.rmtree(workspace_dir, ignore_errors=True)
                continue

            async with self._lock:
                if not self._available_ports:
                    logger.warning("No ports left to restore sandbox %s", name)
                    continue
                port = self._available_ports.pop()

            info = SandboxInfo(session_id=name, workspace_dir=workspace_dir, port=port)
            sandbox = self._create_sandbox_instance(info)
            self._sandboxes[name] = sandbox
            logger.info("Restored sandbox for session %s (port %d)", name, port)

        # Rewrite vite config (session-specific base path) and restart dev servers
        for name, sandbox in self._sandboxes.items():
            if os.path.isfile(os.path.join(sandbox.workspace_dir, "package.json")):
                stamp_vite_config(name, sandbox.workspace_dir)
                asyncio.create_task(sandbox.start_dev_server())

    async def destroy_all(self, *, delete_workspaces: bool = False) -> None:
        session_ids = list(self._sandboxes.keys())
        for sid in session_ids:
            await self.destroy_sandbox(sid, delete_workspace=delete_workspaces)


sandbox_manager = SandboxManager()
