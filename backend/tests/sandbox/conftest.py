import pytest

from flow44.sandbox.base import BaseSandbox, SandboxInfo
from flow44.sandbox.filesystem_mixin import FileSystemMixin
from flow44.sandbox.pnpm_mixin import PnpmMixin
from flow44.sandbox.search_mixin import SearchMixin


class DummySandbox(PnpmMixin, SearchMixin, FileSystemMixin, BaseSandbox):
    """Maximally-capable test sandbox: includes all mixins, all abstract methods raise."""

    def exec(self, command: str):  # type: ignore[override]
        raise NotImplementedError

    async def _spawn_background(self, name: str, command: str, env: dict[str, str]) -> None:
        raise NotImplementedError

    def create_pty(self):  # type: ignore[override]
        raise NotImplementedError

    @classmethod
    def find_pids_in_port_range(cls, port_start: int, port_end: int) -> list[tuple[int, int]]:
        raise NotImplementedError

    @classmethod
    def kill_pid(cls, pid: int) -> None:
        raise NotImplementedError


@pytest.fixture
def sandbox(tmp_path):  # type: ignore[type-arg]
    """Default sandbox fixture: workspace_dir points directly at tmp_path."""
    info = SandboxInfo(project_id="test", workspace_dir=str(tmp_path), port=0)
    return DummySandbox(info)
