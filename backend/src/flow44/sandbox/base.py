import asyncio
import logging
import os
import shutil
import signal
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import IO

from pydantic import BaseModel

from flow44.sandbox.pty import BasePTY

logger = logging.getLogger(__name__)


class SandboxInfo(BaseModel, frozen=True):
    project_id: str
    workspace_dir: str
    port: int


class BaseSandbox(ABC):
    def __init__(self, info: SandboxInfo) -> None:
        self.info = info
        self._bg_processes: dict[str, asyncio.subprocess.Process] = {}
        self._bg_log_files: dict[str, IO[bytes]] = {}
        self._pty: BasePTY | None = None

    @property
    def project_id(self) -> str:
        return self.info.project_id

    @property
    def workspace_dir(self) -> str:
        return self.info.workspace_dir

    @property
    def port(self) -> int:
        return self.info.port

    # -- Lifecycle --

    async def start(self) -> None:
        os.makedirs(self.workspace_dir, exist_ok=True)

    async def destroy(self, *, delete_workspace: bool = True) -> None:
        await self.stop_all_background_processes()
        self.kill_pty()
        if delete_workspace and os.path.isdir(self.workspace_dir):  # noqa: ASYNC240
            shutil.rmtree(self.workspace_dir, ignore_errors=True)

    # -- Command execution --

    @abstractmethod
    def exec(self, command: str) -> AsyncIterator[str]: ...

    # -- Background processes --

    @abstractmethod
    async def _spawn_background(self, name: str, command: str, env: dict[str, str]) -> None: ...

    # TODO: still kinda complecated. I might want to call the sandbox kill (maybe add kill_process next to our kill_pid)
    @staticmethod
    async def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
        """Kill a process and its entire group, then wait for it to exit."""
        # TODO: verify in windows
        if proc.returncode is not None:
            return
        try:
            if hasattr(os, "getpgid"):
                # Unix: kill the entire process group so child processes are also terminated
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGTERM)
            else:
                # Windows: no process groups, kill directly
                proc.kill()
        except (ProcessLookupError, PermissionError, OSError):
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        try:
            await proc.wait()
        except ProcessLookupError:
            pass

    async def stop_background_process(self, name: str) -> None:
        proc = self._bg_processes.pop(name, None)
        if proc is not None:
            await self._kill_process_tree(proc)
        log_file = self._bg_log_files.pop(name, None)
        if log_file is not None:
            try:
                log_file.close()
            except Exception:
                logger.debug("Failed to close log file for %s", name, exc_info=True)

    async def stop_all_background_processes(self) -> None:
        names = list(self._bg_processes.keys())
        for name in names:
            await self.stop_background_process(name)

    def is_background_process_running(self, name: str) -> bool:
        proc = self._bg_processes.get(name)
        return proc is not None and proc.returncode is None

    @classmethod
    @abstractmethod
    def find_pids_in_port_range(cls, port_start: int, port_end: int) -> list[tuple[int, int]]:
        """Return (pid, port) pairs for processes using ports in [port_start, port_end]."""
        ...

    @classmethod
    @abstractmethod
    def kill_pid(cls, pid: int) -> None:
        """Terminate a process by PID."""
        ...

    def get_background_log_path(self, name: str) -> str:
        return os.path.join(self.workspace_dir, f".{name}.log")

    # -- PTY --

    @abstractmethod
    def create_pty(self) -> BasePTY: ...

    def get_or_create_pty(self) -> BasePTY:
        if self._pty is not None:
            if self._pty.is_alive():
                return self._pty
            self.kill_pty()
        self._pty = self.create_pty()
        return self._pty

    def kill_pty(self) -> None:
        if self._pty is not None:
            self._pty.kill()
            self._pty = None

    # -- File I/O --

    def _safe_path(self, relative_path: str) -> str:
        workspace = os.path.realpath(self.workspace_dir)
        cleaned = relative_path.lstrip("/\\")
        target = os.path.realpath(os.path.join(workspace, cleaned))
        # Use os.path.commonpath to safely compare across platforms
        try:
            common = os.path.commonpath([workspace, target])
        except ValueError as exc:
            # Different drives on Windows
            raise PermissionError(f"Path traversal detected: {relative_path}") from exc
        if common != workspace:
            raise PermissionError(f"Path traversal detected: {relative_path}")
        return target
