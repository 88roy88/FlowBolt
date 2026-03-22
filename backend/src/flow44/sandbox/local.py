from __future__ import annotations

import asyncio
import fcntl
import logging
import os
from collections.abc import AsyncIterator

from flow44.sandbox.base import Sandbox, _ensure_bashrc
from flow44.sandbox.pty import PtyHandle, _active_ptys

logger = logging.getLogger(__name__)


class LocalSandbox(Sandbox):
    async def exec(self, command: str) -> AsyncIterator[str]:
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

    async def start_dev_server(self) -> None:
        await self.stop_dev_server()

        log_path = os.path.join(self.workspace_dir, ".dev-server.log")
        self._dev_log_file = open(log_path, "wb")  # noqa: ASYNC230, SIM115

        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"

        dev_cmd = f"pnpm dev --port {self.port} --host 0.0.0.0"
        self._dev_process = await asyncio.create_subprocess_exec(
            "/bin/bash",
            "-c",
            f"cd {self.workspace_dir} && {dev_cmd}",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=self._dev_log_file,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        logger.info(
            "Dev server started for session %s on port %d (pid %s)",
            self.session_id,
            self.port,
            self._dev_process.pid,
        )

    def create_pty(self) -> PtyHandle:
        master_fd, slave_fd = os.openpty()

        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["CLICOLOR"] = "1"
        env["LSCOLORS"] = "GxFxCxDxBxegedabagaced"
        env["HOME"] = self.workspace_dir

        bashrc_path = _ensure_bashrc(self.workspace_dir)

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
            os.execvpe("/bin/bash", ["/bin/bash", "--rcfile", bashrc_path], env)  # noqa: S606

        os.close(slave_fd)

        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        handle = PtyHandle(read_fd=master_fd, write_fd=master_fd, pid=pid, session_id=self.session_id)
        _active_ptys.add(handle)
        return handle
