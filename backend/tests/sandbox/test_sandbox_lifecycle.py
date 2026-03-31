"""Tests for Sandbox base lifecycle: start, destroy."""

import pytest

from flow44.sandbox.base import SandboxInfo

from .conftest import DummySandbox


@pytest.fixture
def sandbox(tmp_path):  # type: ignore[type-arg]
    workspace = tmp_path / "workspace"
    info = SandboxInfo(project_id="test", workspace_dir=str(workspace), port=0)
    return DummySandbox(info)


@pytest.mark.asyncio
class TestSandboxLifecycle:
    async def test_start_creates_workspace_dir(self, sandbox: DummySandbox, tmp_path) -> None:  # type: ignore[type-arg]
        workspace = tmp_path / "workspace"
        assert not workspace.exists()
        await sandbox.start()
        assert workspace.exists()

    async def test_start_is_idempotent(self, sandbox: DummySandbox, tmp_path) -> None:  # type: ignore[type-arg]
        await sandbox.start()
        await sandbox.start()  # second call must not raise
        assert (tmp_path / "workspace").exists()

    async def test_destroy_deletes_workspace(self, sandbox: DummySandbox, tmp_path) -> None:  # type: ignore[type-arg]
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "file.txt").write_text("data")
        await sandbox.destroy(delete_workspace=True)
        assert not workspace.exists()

    async def test_destroy_keeps_workspace(self, sandbox: DummySandbox, tmp_path) -> None:  # type: ignore[type-arg]
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "file.txt").write_text("data")
        await sandbox.destroy(delete_workspace=False)
        assert workspace.exists()

    async def test_destroy_nonexistent_workspace_no_error(self, sandbox: DummySandbox) -> None:
        # workspace was never created — destroy should not raise
        await sandbox.destroy(delete_workspace=True)

    async def test_properties(self, sandbox: DummySandbox) -> None:
        assert sandbox.project_id == "test"
        assert sandbox.port == 0
        assert "workspace" in sandbox.workspace_dir
