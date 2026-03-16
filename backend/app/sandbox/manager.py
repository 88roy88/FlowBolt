"""Sandbox lifecycle manager (singleton)."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from dataclasses import dataclass

from app.config import settings
from app.sandbox.nsjail import build_nsjail_command

logger = logging.getLogger(__name__)


@dataclass
class SandboxInfo:
    """Runtime information for a single sandbox."""

    session_id: str
    workspace_dir: str
    port: int
    process: asyncio.subprocess.Process | None = None
    dev_process: asyncio.subprocess.Process | None = None


class SandboxManager:
    """Manages sandbox creation, lookup, and teardown.

    Maintains a pool of available ports and a registry of active sandboxes.
    Designed as a singleton — import :pydata:`sandbox_manager` from this module.
    """

    def __init__(self) -> None:
        self._sandboxes: dict[str, SandboxInfo] = {}
        self._available_ports: set[int] = set(
            range(settings.SANDBOX_PORT_RANGE_START, settings.SANDBOX_PORT_RANGE_END + 1)
        )
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_sandbox(self, session_id: str) -> SandboxInfo:
        """Create a workspace directory, allocate a port, and start a long-lived
        bash shell process inside nsjail (or a plain subprocess in fallback mode).
        """
        async with self._lock:
            if session_id in self._sandboxes:
                return self._sandboxes[session_id]

            if not self._available_ports:
                raise RuntimeError("No available ports in the sandbox pool")

            port = self._available_ports.pop()

        workspace_dir = os.path.join(settings.WORKSPACE_BASE_DIR, session_id)
        os.makedirs(workspace_dir, exist_ok=True)

        cmd = build_nsjail_command(session_id, workspace_dir, port, command=None)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        info = SandboxInfo(
            session_id=session_id,
            workspace_dir=workspace_dir,
            port=port,
            process=process,
        )

        self._sandboxes[session_id] = info
        return info

    async def destroy_sandbox(self, session_id: str, *, delete_workspace: bool = True) -> None:
        """Kill the sandbox process, free the port, and optionally remove the workspace.

        Parameters
        ----------
        delete_workspace:
            When *False* the workspace directory is preserved on disk.  This is
            used during hot-reload / graceful shutdown so files aren't lost.
        """
        async with self._lock:
            info = self._sandboxes.pop(session_id, None)

        if info is None:
            return

        # Terminate the dev server
        if info.dev_process is not None and info.dev_process.returncode is None:
            try:
                info.dev_process.kill()
                await info.dev_process.wait()
            except ProcessLookupError:
                pass

        # Terminate the long-lived shell process
        if info.process is not None and info.process.returncode is None:
            try:
                info.process.kill()
                await info.process.wait()
            except ProcessLookupError:
                pass

        # Return port to pool
        async with self._lock:
            self._available_ports.add(info.port)

        # Clean up workspace only when explicitly requested
        if delete_workspace and os.path.isdir(info.workspace_dir):
            shutil.rmtree(info.workspace_dir, ignore_errors=True)

    async def start_dev_server(self, session_id: str) -> None:
        """Start `pnpm dev` on the sandbox's allocated port as a background process."""
        info = self._sandboxes.get(session_id)
        if info is None:
            logger.warning("Cannot start dev server: no sandbox for %s", session_id)
            return

        # Kill existing dev server if running
        if info.dev_process is not None and info.dev_process.returncode is None:
            try:
                info.dev_process.kill()
                await info.dev_process.wait()
            except ProcessLookupError:
                pass

        cmd = build_nsjail_command(
            session_id,
            info.workspace_dir,
            info.port,
            command=f"pnpm dev --port {info.port} --host 0.0.0.0",
        )

        info.dev_process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        logger.info(
            "Dev server started for session %s on port %d (pid %s)",
            session_id, info.port, info.dev_process.pid,
        )

    def get_sandbox(self, session_id: str) -> SandboxInfo | None:
        """Look up sandbox info by session id (non-blocking)."""
        return self._sandboxes.get(session_id)

    async def restore_existing_workspaces(self) -> None:
        """Re-register sandboxes for workspace directories that already exist on disk.

        Called on startup so that after a uvicorn reload the file APIs still work
        for sessions whose workspace was preserved.
        """
        base = settings.WORKSPACE_BASE_DIR
        if not os.path.isdir(base):
            return

        for name in os.listdir(base):
            workspace_dir = os.path.join(base, name)
            if not os.path.isdir(workspace_dir):
                continue
            if name in self._sandboxes:
                continue

            async with self._lock:
                if not self._available_ports:
                    logger.warning("No ports left to restore sandbox %s", name)
                    continue
                port = self._available_ports.pop()

            info = SandboxInfo(
                session_id=name,
                workspace_dir=workspace_dir,
                port=port,
                process=None,  # no live process — commands will spawn one-shot
            )
            self._sandboxes[name] = info
            logger.info("Restored sandbox for session %s (port %d)", name, port)

        # Restart dev servers in the background (don't block startup)
        for name, info in self._sandboxes.items():
            if os.path.isfile(os.path.join(info.workspace_dir, "package.json")):
                asyncio.create_task(self.start_dev_server(name))

    async def destroy_all(self, *, delete_workspaces: bool = False) -> None:
        """Tear down every active sandbox.  Used during application shutdown.

        By default workspaces are preserved so hot-reloads don't lose user files.
        Pass ``delete_workspaces=True`` for a full cleanup.
        """
        session_ids = list(self._sandboxes.keys())
        for sid in session_ids:
            await self.destroy_sandbox(sid, delete_workspace=delete_workspaces)


# Module-level singleton
sandbox_manager = SandboxManager()
