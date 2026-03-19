from __future__ import annotations

import asyncio
import os
import subprocess
from collections.abc import AsyncIterator

from app.config import settings
from app.sandbox.base import Sandbox


def _build_nsjail_args(
    session_id: str,
    workspace_dir: str,
    port: int,
    command: str | None = None,
) -> list[str]:
    args: list[str] = [
        settings.NSJAIL_BIN,
        "--mode", "o",
        "--chroot", "/",
        "--cwd", "/home/project",
        "-R", "/usr",
        "-R", "/lib",
        "-R", "/lib64",
        "-R", "/bin",
        "-R", "/sbin",
        "-B", f"{workspace_dir}:/home/project",
        "--cgroup_mem_max", str(settings.SANDBOX_MEMORY_LIMIT_MB * 1024 * 1024),
        "--cgroup_pids_max", str(settings.SANDBOX_PID_LIMIT),
        "--cgroup_mem_mount", "/sys/fs/cgroup/memory",
        "--cgroup_pids_mount", "/sys/fs/cgroup/pids",
        "--time_limit", str(settings.MAX_COMMAND_TIMEOUT),
        "--log_fd", "2",
        "--rlimit_as", "hard",
        "--rlimit_cpu", "hard",
        "--rlimit_fsize", "hard",
        "--rlimit_nofile", "hard",
        "--hostname", f"sandbox-{session_id[:8]}",
        "--disable_clone_newnet",
        "--",
    ]

    if command is None:
        args.append("/bin/bash")
    else:
        args.extend(["/bin/bash", "-c", command])

    return args


class NamespacedSandbox(Sandbox):

    async def exec(self, command: str) -> AsyncIterator[str]:
        cmd = _build_nsjail_args(self.session_id, self.workspace_dir, self.port, command=command)
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
        cmd = _build_nsjail_args(
            self.session_id,
            self.workspace_dir,
            self.port,
            command=f"pnpm dev --port {self.port} --host 0.0.0.0",
        )

        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"

        return await asyncio.create_subprocess_exec(
            *cmd,
            stdout=self._dev_log_file,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )

    def _spawn_pty(self, master_fd: int, slave_fd: int, env: dict[str, str], bashrc_path: str) -> int:
        env["HOME"] = "/home/project"

        cmd = _build_nsjail_args(self.session_id, self.workspace_dir, self.port, command=None)
        proc = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid,
            env=env,
        )
        return proc.pid
