from __future__ import annotations

from flow44.sandbox.pty import WinPTY


class FakeWinptyProcess:
    def __init__(self, chunks: list[str]) -> None:
        self.pid = 1234
        self._chunks = chunks

    def isalive(self) -> bool:
        return True

    def read(self, size: int) -> str:
        return self._chunks.pop(0) if self._chunks else ""

    def close(self, force: bool = False) -> None:
        pass


class TestWinPTYScrollback:
    def test_read_records_scrollback(self) -> None:
        pty = WinPTY(winpty_process=FakeWinptyProcess(["$ ls\r\n", "a.txt\r\n"]))
        try:
            assert pty.read() == b"$ ls\r\n"
            assert pty.read() == b"a.txt\r\n"
            assert pty.read() == b""
            assert pty.get_scrollback() == b"$ ls\r\na.txt\r\n"
        finally:
            pty.kill()
