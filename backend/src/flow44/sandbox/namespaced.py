import asyncio
import fcntl
import logging
import os
import subprocess
from collections.abc import AsyncIterator

from flow44.config import settings
from flow44.sandbox.base import _ensure_bashrc
from flow44.sandbox.pty import PtyHandle, _active_ptys
from flow44.sandbox.unix_local import UnixSandbox

logger = logging.getLogger(__name__)


def _can_use_cgroupv2() -> bool:
    try:
        with open("/sys/fs/cgroup/cgroup.subtree_control", "w") as f:
            f.write("+memory +pids")
        return True
    except OSError:
        return False


_CGROUPV2_AVAILABLE = _can_use_cgroupv2() if not settings.SANDBOX_DISABLE_CGROUPS else False


def _build_nsjail_args(
    project_id: str,
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
        "--mode",
        "o",
        "-R",
        "/usr",
        "-R",
        "/usr/local",
        "-R",
        "/lib",
        *(["-R", "/lib64"] if os.path.exists("/lib64") else []),
        "-R",
        "/bin",
        "-R",
        "/sbin",
        "-R",
        "/etc",
        "--mount",
        "none:/tmp:tmpfs:rw",
        "-R",
        "/dev",
        "-B",
        f"{workspace_dir}:/home/project",
        "-B",
        f"{settings.PNPM_STORE_DIR}:/pnpm-store",
        "--mount",
        "none:/home/appuser:tmpfs:rw",
        "--cwd",
        "/home/project",
        "--env",
        "HOME=/home/appuser",
        "--env",
        "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "--env",
        "TERM=xterm-256color",
        "--env",
        "FORCE_COLOR=1",
        "--time_limit",
        str(time_limit),
        "--log",
        os.path.join(workspace_dir, ".nsjail.log"),
        "--rlimit_as",
        "soft",
        "--rlimit_cpu",
        "hard",
        "--rlimit_fsize",
        "soft",
        "--rlimit_nofile",
        "soft",
        "--hostname",
        f"sandbox-{project_id[:8]}",
        "--disable_clone_newnet",
        "--user",
        "1000:1000:1",
        "--group",
        "1000:1000:1",
        "--disable_proc",
    ]

    if _CGROUPV2_AVAILABLE:
        args.extend(
            [
                "--use_cgroupv2",
                "--cgroup_mem_max",
                str(mem_limit),
                "--cgroup_pids_max",
                str(pid_limit),
            ]
        )
    else:
        args.append("--disable_clone_newcgroup")

    args.append("--")

    if command is None:
        args.extend(["/bin/bash", "--rcfile", "/home/project/.bashrc"])
    else:
        args.extend(["/bin/bash", "-c", command])

    return args


class NamespacedSandbox(UnixSandbox):
    # TODO: override find_pids_in_port_range with a nsjail-aware approach:
    #   pgrep -f nsjail would find ALL orphaned nsjail processes regardless of port,
    #   including ones spawned via the terminal that never bound a port.
    #   In namespaced mode we own every nsjail process on the host, so killing all of
    #   them is safe and complete. Port-based detection (lsof) misses terminal-spawned
    #   processes and can have false positives from unrelated services.

    async def exec(self, command: str) -> AsyncIterator[str]:
        cmd = _build_nsjail_args(self.project_id, self.workspace_dir, self.port, command=command)
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

    async def _spawn_background(self, name: str, command: str, env: dict[str, str]) -> None:
        log_path = self.get_background_log_path(name)
        log_file = open(log_path, "wb")  # noqa: ASYNC230, SIM115

        cmd = _build_nsjail_args(
            self.project_id,
            self.workspace_dir,
            self.port,
            command=command,
            time_limit=0,
        )

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=log_file,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )

        self._bg_processes[name] = proc
        self._bg_log_files[name] = log_file
        logger.debug("Background process '%s' started (pid %s)", name, proc.pid)

    def create_pty(self) -> PtyHandle:
        master_fd, slave_fd = os.openpty()

        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["CLICOLOR"] = "1"
        env["LSCOLORS"] = "GxFxCxDxBxegedabagaced"
        env["HOME"] = "/home/project"

        _ensure_bashrc(self.workspace_dir)

        cmd = _build_nsjail_args(self.project_id, self.workspace_dir, self.port, command=None, time_limit=0)
        proc = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid,  # noqa: PLW1509
            env=env,
        )

        os.close(slave_fd)

        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        handle = PtyHandle(read_fd=master_fd, write_fd=master_fd, pid=proc.pid, project_id=self.project_id)
        _active_ptys.add(handle)
        return handle
