from __future__ import annotations

import asyncio
import os
import subprocess
from collections.abc import AsyncIterator

from app.config import settings
from app.sandbox.base import Sandbox


def _can_use_cgroupv2() -> bool:
    """Check if we can write to cgroup v2 subtree_control (requires privileged or proper delegation)."""
    try:
        with open("/sys/fs/cgroup/cgroup.subtree_control", "w") as f:
            f.write("+memory +pids")
        return True
    except OSError:
        return False


# Cache the cgroup check at module load — it won't change during runtime.
_CGROUPV2_AVAILABLE = _can_use_cgroupv2() if not os.environ.get("AIB_SANDBOX_DISABLE_CGROUPS") else False


def _build_nsjail_args(
    session_id: str,
    workspace_dir: str,
    port: int,
    command: str | None = None,
    *,
    time_limit: int | None = None,
) -> list[str]:
    mem_limit = settings.SANDBOX_MEMORY_LIMIT_MB * 1024 * 1024
    pid_limit = settings.SANDBOX_PID_LIMIT
    if time_limit is None:
        time_limit = settings.MAX_COMMAND_TIMEOUT

    args: list[str] = [
        settings.NSJAIL_BIN,
        "--mode", "o",
        # Explicit mounts (no --chroot) for user namespace compatibility
        "-R", "/usr",
        "-R", "/usr/local",
        "-R", "/lib",
        *(["-R", "/lib64"] if os.path.exists("/lib64") else []),
        "-R", "/bin",
        "-R", "/sbin",
        "-R", "/etc",
        "--mount", "none:/tmp:tmpfs:rw",
        "-R", "/dev",
        "-B", f"{workspace_dir}:/home/project",
        # pnpm/node need a writable home for cache and store
        "--mount", "none:/home/appuser:tmpfs:rw",
        "--cwd", "/home/project",
        "--env", "HOME=/home/appuser",
        "--env", "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "--env", "TERM=xterm-256color",
        "--env", "FORCE_COLOR=1",
        "--time_limit", str(time_limit),
        "--log", "/dev/null",
        "--rlimit_as", "soft",
        "--rlimit_cpu", "hard",
        "--rlimit_fsize", "soft",
        "--rlimit_nofile", "soft",
        "--hostname", f"sandbox-{session_id[:8]}",
        "--disable_clone_newnet",
        # Map UID/GID 1000 inside → 1000 outside so workspace files are writable
        "--user", "1000:1000:1",
        "--group", "1000:1000:1",
        # /proc remount fails in Docker Desktop user namespaces; skip it.
        # PID isolation still works via clone_newpid.
        "--disable_proc",
    ]

    if _CGROUPV2_AVAILABLE:
        args.extend([
            "--use_cgroupv2",
            "--cgroup_mem_max", str(mem_limit),
            "--cgroup_pids_max", str(pid_limit),
        ])
    else:
        args.append("--disable_clone_newcgroup")

    args.append("--")

    if command is None:
        args.extend(["/bin/bash", "--rcfile", "/home/project/.bashrc"])
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
            time_limit=0,
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

        cmd = _build_nsjail_args(self.session_id, self.workspace_dir, self.port, command=None, time_limit=0)
        proc = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid,
            env=env,
        )
        return proc.pid
