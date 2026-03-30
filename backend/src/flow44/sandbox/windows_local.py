import asyncio
import logging
import os
import subprocess
from collections.abc import AsyncIterator

from flow44.sandbox.base import BaseSandbox
from flow44.sandbox.pty import WinPTY

if os.name == "nt":
    try:
        from winpty import PtyProcess as WinPtyProcess
    except ImportError as e:
        raise ImportError(
            "winpty package is required for Windows sandbox support. Install it with: pip install pywinpty"
        ) from e

logger = logging.getLogger(__name__)


class _PopenWrapper:
    """Minimal wrapper so subprocess.Popen looks like asyncio.subprocess.Process."""

    def __init__(self, proc: subprocess.Popen[str] | subprocess.Popen[bytes]) -> None:
        self._proc = proc

    @property
    def pid(self) -> int:
        return self._proc.pid

    @property
    def returncode(self) -> int | None:
        return self._proc.returncode

    def kill(self) -> None:
        subprocess.run(["taskkill", "/PID", str(self._proc.pid), "/T", "/F"], check=False)  # noqa: S607

    async def wait(self) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._proc.wait)


class WindowsLocalSandbox(BaseSandbox):
    async def exec(self, command: str) -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        cmd = f"cd /d {self.workspace_dir} && {command}"

        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(  # noqa: PLW1510
                ["cmd", "/c", cmd],  # noqa: S607
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self.workspace_dir,
            ),
        )

        for line in result.stdout.splitlines():
            yield line + "\n"

    async def _spawn_background(self, name: str, command: str, env: dict[str, str]) -> None:
        log_path = self.get_background_log_path(name)
        log_file = open(log_path, "wb")  # noqa: ASYNC230, SIM115

        cmd = f"cd /d {self.workspace_dir} && {command}"
        proc = subprocess.Popen(  # noqa: ASYNC220
            ["cmd", "/c", cmd],  # noqa: S607
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            encoding="utf-8",
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # type: ignore[attr-defined]  # Windows-only
        )

        self._bg_processes[name] = _PopenWrapper(proc)  # type: ignore[assignment]
        self._bg_log_files[name] = log_file
        logger.debug("Background process '%s' started (pid %s)", name, proc.pid)

    @classmethod
    def find_pids_in_port_range(cls, port_start: int, port_end: int) -> list[tuple[int, int]]:
        """Return (pid, port) pairs via netstat -ano (Windows)."""
        try:
            result = subprocess.run(  # noqa: PLW1510
                ["netstat", "-ano"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=5,
            )
            pairs: list[tuple[int, int]] = []
            for line in result.stdout.splitlines():
                parts = line.split()
                # netstat -ano: Proto  Local  Foreign  State  PID
                if len(parts) < 5 or parts[3] != "LISTENING":
                    continue
                try:
                    port = int(parts[1].rsplit(":", 1)[1])
                    pid = int(parts[4])
                    if port_start <= port <= port_end:
                        pairs.append((pid, port))
                except (ValueError, IndexError):
                    continue
            return pairs
        except FileNotFoundError:
            return []
        except Exception:
            logger.debug("Failed to find pids in port range on Windows", exc_info=True)
            return []

    @classmethod
    def kill_pid(cls, pid: int) -> None:
        """Terminate a process tree via taskkill (Windows)."""
        try:
            subprocess.run(  # noqa: PLW1510, S603
                ["taskkill", "/PID", str(pid), "/T", "/F"],  # noqa: S607
                capture_output=True,
                timeout=5,
            )
        except Exception:  # noqa: S110
            pass

    def create_pty(self) -> WinPTY:
        proc = WinPtyProcess.spawn("cmd.exe", cwd=self.workspace_dir)
        pty = WinPTY(winpty_process=proc)
        return pty
