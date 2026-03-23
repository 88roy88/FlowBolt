from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal

from flow44.config import settings
from flow44.sandbox.base import Sandbox, SandboxInfo

logger = logging.getLogger(__name__)


def stamp_vite_config(project_id: str, workspace_dir: str) -> None:
    """Read vite.config.ts from the template and replace the project ID placeholder."""
    template_path = os.path.join(settings.TEMPLATE_DIR, "vite.config.ts")
    with open(template_path, encoding="utf-8") as f:
        content = f.read()
    dest_path = os.path.join(workspace_dir, "vite.config.ts")
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(content.replace("{{PROJECT_ID}}", project_id))


class SandboxManager:
    def __init__(self) -> None:
        self._sandboxes: dict[str, Sandbox] = {}
        self._available_ports: set[int] = set(
            range(settings.SANDBOX_PORT_RANGE_START, settings.SANDBOX_PORT_RANGE_END + 1)
        )
        self._lock = asyncio.Lock()
        self._ensure_pnpm_store()

    @staticmethod
    def _ensure_pnpm_store() -> None:
        try:
            os.makedirs(settings.PNPM_STORE_DIR, exist_ok=True)
        except OSError:
            logger.warning("Could not create pnpm store dir: %s", settings.PNPM_STORE_DIR)

    def _create_sandbox_instance(self, info: SandboxInfo) -> Sandbox:
        # TODO: why the imports are here and not top level?
        if settings.SANDBOX_MODE == "namespaced":
            from flow44.sandbox.namespaced import NamespacedSandbox  # noqa: PLC0415

            return NamespacedSandbox(info)
        if os.name == "nt":
            from flow44.sandbox.windows_local import WindowsLocalSandbox  # noqa: PLC0415

            return WindowsLocalSandbox(info)
        from flow44.sandbox.local import LocalSandbox  # noqa: PLC0415

        return LocalSandbox(info)

    async def create_sandbox(self, project_id: str) -> Sandbox:
        async with self._lock:
            if project_id in self._sandboxes:
                return self._sandboxes[project_id]

            if not self._available_ports:
                raise RuntimeError("No available ports in the sandbox pool")

            port = self._available_ports.pop()

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

    def get_sandbox(self, project_id: str) -> Sandbox | None:
        return self._sandboxes.get(project_id)

    @staticmethod
    def _kill_stale_dev_servers() -> None:  # noqa: C901
        """Find orphan pnpm dev processes in our port range and kill them."""
        import subprocess as _sp  # noqa: PLC0415

        port_start = settings.SANDBOX_PORT_RANGE_START
        port_end = settings.SANDBOX_PORT_RANGE_END
        try:
            result = _sp.run(  # noqa: PLW1510
                ["pgrep", "-f", "pnpm dev --port"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return
            for pid_str in result.stdout.strip().splitlines():
                pid = int(pid_str.strip())
                try:
                    cmdline = _sp.run(  # noqa: PLW1510
                        ["ps", "-p", str(pid), "-o", "args="],  # noqa: S607
                        capture_output=True,
                        text=True,
                        timeout=5,
                    ).stdout.strip()
                except Exception:  # noqa: S112
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

    async def restore_existing_workspaces(self, live_project_ids: set[str]) -> None:  # noqa: C901
        """Re-register sandboxes for workspaces that survived a restart.

        Orphan directories (not in live_project_ids) are deleted.
        """
        if os.name != "nt":
            self._kill_stale_dev_servers()

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

            async with self._lock:
                if not self._available_ports:
                    logger.warning("No ports left to restore sandbox %s", name)
                    continue
                port = self._available_ports.pop()

            info = SandboxInfo(project_id=name, workspace_dir=workspace_dir, port=port)
            sandbox = self._create_sandbox_instance(info)
            self._sandboxes[name] = sandbox
            logger.info("Restored sandbox for session %s (port %d)", name, port)

        # Rewrite vite config (session-specific base path) and restart dev servers
        for name, sandbox in self._sandboxes.items():
            if os.path.isfile(os.path.join(sandbox.workspace_dir, "package.json")):  # noqa: ASYNC240
                stamp_vite_config(name, sandbox.workspace_dir)
                asyncio.create_task(sandbox.start_dev_server())

    async def destroy_all(self, *, delete_workspaces: bool = False) -> None:
        project_ids = list(self._sandboxes.keys())
        for sid in project_ids:
            await self.destroy_sandbox(sid, delete_workspace=delete_workspaces)


sandbox_manager = SandboxManager()
