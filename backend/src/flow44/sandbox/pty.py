from __future__ import annotations

import atexit
import logging
import os
import signal
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# 64 KiB scrollback so reconnecting clients see recent output.
SCROLLBACK_SIZE = 65536


@dataclass(eq=False)
class PtyHandle:
    read_fd: int = -1
    write_fd: int = -1
    pid: int = -1
    project_id: str = ""
    winpty_process: Any | None = field(default=None, repr=False)  # pywinpty PtyProcess (optional dep)
    _scrollback: deque[bytes] = field(default_factory=deque, repr=False)
    _scrollback_bytes: int = field(default=0, repr=False)

    @property
    def is_winpty(self) -> bool:
        return self.winpty_process is not None

    def alive(self) -> bool:
        """Return True if the underlying process is still running."""
        wp = self.winpty_process
        if wp is not None:
            return bool(wp.isalive())
        if self.pid <= 0:
            return False
        try:
            pid, _ = os.waitpid(self.pid, os.WNOHANG)
            return pid == 0  # 0 means still running
        except ChildProcessError:
            return False

    def read(self, size: int = 4096) -> bytes:
        wp = self.winpty_process
        if wp is not None:
            try:
                if not wp.isalive():
                    return b""
                return wp.read(size).encode("utf-8", errors="replace")  # type: ignore[no-any-return]
            except Exception:
                return b""
        try:
            data = os.read(self.read_fd, size)
        except (BlockingIOError, OSError):
            return b""
        if data:
            self._push_scrollback(data)
        return data

    def write(self, data: bytes) -> None:
        wp = self.winpty_process
        if wp is not None:
            wp.write(data.decode("utf-8", errors="replace"))
            return
        os.write(self.write_fd, data)

    def get_scrollback(self) -> bytes:
        """Return the scrollback buffer contents."""
        return b"".join(self._scrollback)

    def _push_scrollback(self, data: bytes) -> None:
        self._scrollback.append(data)
        self._scrollback_bytes += len(data)
        while self._scrollback_bytes > SCROLLBACK_SIZE:
            removed = self._scrollback.popleft()
            self._scrollback_bytes -= len(removed)

    def kill(self) -> None:
        wp = self.winpty_process
        if wp is not None:
            try:
                if wp.isalive():
                    wp.close(force=True)
            except Exception:
                logger.debug("Failed to close winpty process", exc_info=True)
            return
        try:
            os.close(self.read_fd)
        except OSError:
            pass
        self._terminate_process()

    def _terminate_process(self) -> None:
        """Kill the PTY process. Handles both Unix (killpg) and Windows (kill)."""
        try:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(self.pid), signal.SIGTERM)
            else:
                os.kill(self.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                os.kill(self.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        if hasattr(os, "waitpid"):
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
