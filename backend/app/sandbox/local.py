from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

from app.sandbox.base import Sandbox

if os.name != "nt":
    import fcntl  # type: ignore[import-not-found]


class LocalSandbox(Sandbox):

    async def exec(self, command: str) -> AsyncIterator[str]:
        if os.name == "nt":
            cmd = ["cmd", "/c", f"cd /d {self.workspace_dir} && {command}"]
        else:
            cmd = ["/bin/bash", "-c", f"cd {self.workspace_dir} && {command}"]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        if proc.stdout is None:
            return
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            yield line.decode(errors="replace")

        await proc.wait()

    async def _spawn_dev_server(self) -> asyncio.subprocess.Process:
        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"

        if os.name == "nt":
            dev_cmd = f"cd /d {self.workspace_dir} && pnpm dev --port {self.port} --host 0.0.0.0"
            return await asyncio.create_subprocess_exec(
                "cmd", "/c", dev_cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=self._dev_log_file,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )

        dev_cmd = f"pnpm dev --port {self.port} --host 0.0.0.0"
        return await asyncio.create_subprocess_exec(
            "/bin/bash", "-c", f"cd {self.workspace_dir} && {dev_cmd}",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=self._dev_log_file,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )

    def _spawn_pty(self, master_fd: int, slave_fd: int, env: dict[str, str], bashrc_path: str) -> int:
        env["HOME"] = self.workspace_dir

        pid = os.fork()
        if pid == 0:
            os.close(master_fd)
            os.setsid()
            fcntl.ioctl(slave_fd, __import__("termios").TIOCSCTTY, 0)
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            if slave_fd > 2:
                os.close(slave_fd)
            os.chdir(self.workspace_dir)
            os.execvpe("/bin/bash", ["/bin/bash", "--rcfile", bashrc_path], env)

        return pid
