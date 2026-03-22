from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from collections.abc import AsyncIterator

from flow44.sandbox.base import Sandbox, _ensure_bashrc
from flow44.sandbox.pty import PtyHandle, _active_ptys

logger = logging.getLogger(__name__)


class _PopenWrapper:
    """Minimal wrapper so subprocess.Popen looks like asyncio.subprocess.Process."""

    def __init__(self, proc: subprocess.Popen) -> None:
        self._proc = proc

    @property
    def pid(self) -> int:
        return self._proc.pid

    @property
    def returncode(self) -> int | None:
        return self._proc.returncode

    def kill(self) -> None:
        subprocess.run(["taskkill", "/PID", str(self._proc.pid), "/T", "/F"], check=False)

    async def wait(self) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._proc.wait)


class WindowsLocalSandbox(Sandbox):

    async def exec(self, command: str) -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        cmd = f"cd /d {self.workspace_dir} && {command}"

        result = await loop.run_in_executor(None, lambda: subprocess.run(
            ["cmd", "/c", cmd],
            capture_output=True,
            text=True,
            cwd=self.workspace_dir,
        ))

        for line in result.stdout.splitlines():
            yield line + "\n"

    async def start_dev_server(self) -> None:
        await self.stop_dev_server()

        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"

        log_path = os.path.join(self.workspace_dir, ".dev-server.log")
        log_file = open(log_path, "w")  # noqa: SIM115

        dev_cmd = f"cd /d {self.workspace_dir} && pnpm dev --port {self.port} --host 0.0.0.0"
        proc = subprocess.Popen(
            ["cmd", "/c", dev_cmd],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )

        self._dev_log_file = log_file
        self._dev_process = _PopenWrapper(proc)  # type: ignore[assignment]
        logger.info(
            "Dev server started for session %s on port %d (pid %s)",
            self.session_id, self.port, proc.pid,
        )

    async def stop_dev_server(self) -> None:
        if self._dev_process is not None:
            self._dev_process.kill()
            await self._dev_process.wait()
            self._dev_process = None
        if self._dev_log_file is not None:
            try:
                self._dev_log_file.close()
            except Exception:
                pass
            self._dev_log_file = None

    def create_pty(self) -> PtyHandle:
        from winpty import PtyProcess as WinPtyProcess  # type: ignore[import-untyped]

        _ensure_bashrc(self.workspace_dir)
        proc = WinPtyProcess.spawn("cmd.exe", cwd=self.workspace_dir)

        handle = PtyHandle(pid=proc.pid, session_id=self.session_id, winpty_process=proc)
        _active_ptys.add(handle)
        return handle
