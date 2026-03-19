from __future__ import annotations

import atexit
import os
import signal
from dataclasses import dataclass, field


@dataclass(eq=False)
class PtyHandle:
    read_fd: int = -1
    write_fd: int = -1
    pid: int = -1
    session_id: str = ""
    winpty_process: object | None = field(default=None, repr=False)

    @property
    def is_winpty(self) -> bool:
        return self.winpty_process is not None

    def read(self, size: int = 4096) -> bytes:
        if self.is_winpty:
            try:
                if not self.winpty_process.isalive():
                    return b""
                return self.winpty_process.read(size).encode("utf-8", errors="replace")
            except Exception:
                return b""
        try:
            return os.read(self.read_fd, size)
        except (BlockingIOError, OSError):
            return b""

    def write(self, data: bytes) -> None:
        if self.is_winpty:
            self.winpty_process.write(data.decode("utf-8", errors="replace"))
            return
        os.write(self.write_fd, data)

    def kill(self) -> None:
        if self.is_winpty:
            try:
                if self.winpty_process.isalive():
                    self.winpty_process.close(force=True)
            except Exception:
                pass
            return
        try:
            os.close(self.read_fd)
        except OSError:
            pass
        try:
            os.killpg(os.getpgid(self.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                os.kill(self.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        try:
            os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            pass


_active_ptys: set[PtyHandle] = set()


def cleanup_all_ptys() -> None:
    for pty in list(_active_ptys):
        _active_ptys.discard(pty)
        pty.kill()


atexit.register(cleanup_all_ptys)
