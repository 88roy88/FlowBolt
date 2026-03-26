from __future__ import annotations

import atexit
import logging
import os
import signal
from abc import ABC, abstractmethod
from collections import deque
from typing import Any, ClassVar

logger = logging.getLogger(__name__)

# 64 KiB scrollback so reconnecting clients see recent output.
SCROLLBACK_SIZE = 65536


class BasePTY(ABC):
    _registry: ClassVar[set[BasePTY]] = set()

    def __init__(self) -> None:
        self._scrollback: deque[bytes] = deque()
        self._scrollback_bytes: int = 0
        BasePTY._registry.add(self)

    @abstractmethod
    def is_alive(self) -> bool: ...

    @abstractmethod
    def read(self, size: int = 4096) -> bytes: ...

    @abstractmethod
    def write(self, data: bytes) -> None: ...

    @abstractmethod
    def _kill(self) -> None: ...

    def kill(self) -> None:
        BasePTY._registry.discard(self)
        self._kill()

    def get_scrollback(self) -> bytes:
        return b"".join(self._scrollback)

    def _push_scrollback(self, data: bytes) -> None:
        self._scrollback.append(data)
        self._scrollback_bytes += len(data)
        while self._scrollback_bytes > SCROLLBACK_SIZE:
            removed = self._scrollback.popleft()
            self._scrollback_bytes -= len(removed)

    @classmethod
    def _cleanup_all(cls) -> None:
        for pty in list(cls._registry):
            pty.kill()


atexit.register(BasePTY._cleanup_all)


class UnixPTY(BasePTY):
    def __init__(self, read_fd: int, write_fd: int, pid: int) -> None:
        super().__init__()
        self.read_fd = read_fd
        self.write_fd = write_fd
        self.pid = pid

    def is_alive(self) -> bool:
        if self.pid <= 0:
            return False
        try:
            pid, _ = os.waitpid(self.pid, os.WNOHANG)
            return pid == 0
        except (ChildProcessError, AttributeError):
            return False

    def read(self, size: int = 4096) -> bytes:
        try:
            data = os.read(self.read_fd, size)
        except (BlockingIOError, OSError):
            return b""
        if data:
            self._push_scrollback(data)
        return data

    def write(self, data: bytes) -> None:
        os.write(self.write_fd, data)

    def _kill(self) -> None:
        try:
            os.close(self.read_fd)
        except OSError:
            pass
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
        if hasattr(os, "waitpid") and hasattr(os, "WNOHANG"):
            try:
                os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                pass


class WinPTY(BasePTY):
    def __init__(self, winpty_process: Any) -> None:
        super().__init__()
        self.pid: int = winpty_process.pid
        self._proc = winpty_process

    def is_alive(self) -> bool:
        try:
            return bool(self._proc.isalive())
        except Exception:
            return False

    def read(self, size: int = 4096) -> bytes:
        try:
            if not self._proc.isalive():
                return b""
            return self._proc.read(size).encode("utf-8", errors="replace")  # type: ignore[no-any-return]
        except Exception:
            return b""

    def write(self, data: bytes) -> None:
        self._proc.write(data.decode("utf-8", errors="replace"))

    def _kill(self) -> None:
        try:
            if self._proc.isalive():
                self._proc.close(force=True)
        except Exception:
            logger.debug("Failed to close winpty process", exc_info=True)
