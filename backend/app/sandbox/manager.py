"""Sandbox lifecycle manager (singleton)."""

from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass, field

from app.config import settings
from app.sandbox.nsjail import build_nsjail_command


@dataclass
class SandboxInfo:
    """Runtime information for a single sandbox."""

    session_id: str
    workspace_dir: str
    port: int
    process: asyncio.subprocess.Process | None = None


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

    async def destroy_sandbox(self, session_id: str) -> None:
        """Kill the sandbox process, free the port, and remove the workspace directory."""
        async with self._lock:
            info = self._sandboxes.pop(session_id, None)

        if info is None:
            return

        # Terminate the long-lived process
        if info.process is not None and info.process.returncode is None:
            try:
                info.process.kill()
                await info.process.wait()
            except ProcessLookupError:
                pass

        # Return port to pool
        async with self._lock:
            self._available_ports.add(info.port)

        # Clean up workspace
        if os.path.isdir(info.workspace_dir):
            shutil.rmtree(info.workspace_dir, ignore_errors=True)

    def get_sandbox(self, session_id: str) -> SandboxInfo | None:
        """Look up sandbox info by session id (non-blocking)."""
        return self._sandboxes.get(session_id)

    async def destroy_all(self) -> None:
        """Tear down every active sandbox.  Used during application shutdown."""
        session_ids = list(self._sandboxes.keys())
        for sid in session_ids:
            await self.destroy_sandbox(sid)


# Module-level singleton
sandbox_manager = SandboxManager()
