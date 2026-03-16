"""nsjail wrapper for sandboxed command execution.

Provides nsjail-based isolation on Linux and a direct subprocess fallback
for development on macOS / systems where nsjail is not available.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

from app.config import settings


def _nsjail_available() -> bool:
    """Return True if the configured nsjail binary exists on disk."""
    return os.path.isfile(settings.NSJAIL_BIN) and os.access(settings.NSJAIL_BIN, os.X_OK)


def build_nsjail_command(
    session_id: str,
    workspace_dir: str,
    port: int,
    command: str | None = None,
) -> list[str]:
    """Build the nsjail CLI argument list.

    Parameters
    ----------
    session_id:
        Unique identifier used for cgroup naming.
    workspace_dir:
        Host path mounted read-write at ``/home/project`` inside the jail.
    port:
        Port to forward from the sandbox network namespace.
    command:
        If *None* a long-lived ``/bin/bash`` shell is started; otherwise the
        given command string is executed via ``/bin/bash -c``.
    """

    if not _nsjail_available():
        # Fallback: run directly without sandboxing (dev / macOS)
        shell_cmd = command if command else "/bin/bash"
        return ["/bin/bash", "-c", f"cd {workspace_dir} && {shell_cmd}"]

    exe = settings.NSJAIL_BIN

    args: list[str] = [
        exe,
        "--mode", "o",  # once mode (or listen mode handled by caller)
        "--chroot", "/",
        "--cwd", "/home/project",
        # Read-only mounts
        "-R", "/usr",
        "-R", "/lib",
        "-R", "/lib64",
        "-R", "/bin",
        "-R", "/sbin",
        # Read-write workspace mount
        "-B", f"{workspace_dir}:/home/project",
        # Cgroup limits
        "--cgroup_mem_max", str(settings.SANDBOX_MEMORY_LIMIT_MB * 1024 * 1024),
        "--cgroup_pids_max", str(settings.SANDBOX_PID_LIMIT),
        "--cgroup_mem_mount", "/sys/fs/cgroup/memory",
        "--cgroup_pids_mount", "/sys/fs/cgroup/pids",
        # Time limit
        "--time_limit", str(settings.MAX_COMMAND_TIMEOUT),
        # Identification
        "--log_fd", "2",
        "--rlimit_as", "hard",
        "--rlimit_cpu", "hard",
        "--rlimit_fsize", "hard",
        "--rlimit_nofile", "hard",
        # Hostname
        "--hostname", f"sandbox-{session_id[:8]}",
        # Network — keep host network but restrict via iptables outside nsjail
        "--disable_clone_newnet",
        "--",
    ]

    if command is None:
        args.append("/bin/bash")
    else:
        args.extend(["/bin/bash", "-c", command])

    return args


async def exec_in_sandbox(session_id: str, command: str) -> AsyncIterator[str]:
    """Execute *command* inside the sandbox for *session_id*.

    If there is no long-lived process for the session we spawn a fresh nsjail
    (or plain subprocess in fallback mode).  Output lines are yielded as they
    arrive.
    """

    from app.sandbox.manager import sandbox_manager  # avoid circular import

    sandbox = sandbox_manager.get_sandbox(session_id)

    if sandbox is not None and sandbox.process is not None and sandbox.process.returncode is None:
        # The sandbox has a live shell — write the command to its stdin and
        # read output until a sentinel marker.
        sentinel = f"__DONE_{os.urandom(4).hex()}__"
        stdin = sandbox.process.stdin
        stdout = sandbox.process.stdout

        if stdin is None or stdout is None:
            # Fall through to fresh-process path
            pass
        else:
            stdin.write(f"{command}; echo {sentinel}\n".encode())
            await stdin.drain()

            while True:
                line = await asyncio.wait_for(stdout.readline(), timeout=settings.MAX_COMMAND_TIMEOUT)
                decoded = line.decode(errors="replace")
                if sentinel in decoded:
                    break
                yield decoded
            return

    # No live shell — spawn a one-shot process
    workspace_dir = sandbox.workspace_dir if sandbox else f"{settings.WORKSPACE_BASE_DIR}/{session_id}"
    port = sandbox.port if sandbox else 0

    cmd = build_nsjail_command(session_id, workspace_dir, port, command=command)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    assert proc.stdout is not None
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        yield line.decode(errors="replace")

    await proc.wait()
