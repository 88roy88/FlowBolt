"""Tests for SandboxManager: create, get, destroy, port lifecycle, stamp_vite_config."""

from unittest.mock import patch

import pytest

from flow44.sandbox.base import SandboxInfo
from flow44.sandbox.manager import SandboxManager

from .conftest import DummySandbox


@pytest.fixture
def manager(tmp_path):  # type: ignore[type-arg]
    workspace_base = str(tmp_path / "workspaces")
    with patch("flow44.sandbox.manager.settings") as mock_s:
        mock_s.SANDBOX_MODE = "local"
        mock_s.SANDBOX_PORT_RANGE_START = 19100
        mock_s.SANDBOX_PORT_RANGE_END = 19110
        mock_s.PNPM_STORE_DIR = str(tmp_path / ".pnpm-store")
        mock_s.WORKSPACE_BASE_DIR = workspace_base
        mgr = SandboxManager()
        yield mgr, workspace_base, mock_s


@pytest.mark.asyncio
class TestSandboxManagerLifecycle:
    async def test_get_creates_if_missing(self, manager) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, mock_s = manager
        with patch("flow44.sandbox.manager.settings", mock_s):
            sandbox = await mgr.get_sandbox("proj1")
        assert "proj1" in mgr._sandboxes
        assert mgr._sandboxes["proj1"] is sandbox

    async def test_get_idempotent(self, manager) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, mock_s = manager
        with patch("flow44.sandbox.manager.settings", mock_s):
            s1 = await mgr.get_sandbox("proj1")
            s2 = await mgr.get_sandbox("proj1")
        assert s1 is s2

    async def test_wake_sandbox_idempotent(self, manager) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, mock_s = manager
        with patch("flow44.sandbox.manager.settings", mock_s):
            s1 = await mgr.wake_sandbox("proj1")
            s2 = await mgr.wake_sandbox("proj1")
        assert s1 is s2

    async def test_suspend_removes_sandbox(self, manager) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, mock_s = manager
        with patch("flow44.sandbox.manager.settings", mock_s):
            await mgr.get_sandbox("proj1")
            await mgr.suspend_sandbox("proj1")
        assert "proj1" not in mgr._sandboxes

    async def test_port_freed_after_suspend(self, manager) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, mock_s = manager
        with patch("flow44.sandbox.manager.settings", mock_s):
            sandbox = await mgr.get_sandbox("proj1")
            port = sandbox.port
            assert port not in mgr._available_ports
            await mgr.suspend_sandbox("proj1")
        assert port in mgr._available_ports

    async def test_suspend_nonexistent_no_error(self, manager) -> None:  # type: ignore[type-arg]
        mgr, *_ = manager
        await mgr.suspend_sandbox("ghost")  # must not raise

    async def test_suspend_all(self, manager) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, mock_s = manager
        with patch("flow44.sandbox.manager.settings", mock_s):
            await mgr.get_sandbox("p1")
            await mgr.get_sandbox("p2")
            await mgr.suspend_all()
        assert "p1" not in mgr._sandboxes
        assert "p2" not in mgr._sandboxes

    async def test_workspace_dir_is_under_base(self, manager) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, mock_s = manager
        with patch("flow44.sandbox.manager.settings", mock_s):
            sandbox = await mgr.get_sandbox("myproject")
        assert sandbox.workspace_dir.startswith(workspace_base)
        assert "myproject" in sandbox.workspace_dir


class TestStampViteConfig:
    def test_replaces_placeholder(self, tmp_path) -> None:  # type: ignore[type-arg]
        template_dir = tmp_path / "template"
        template_dir.mkdir()
        (template_dir / "vite.config.ts").write_text("base: '/{{PROJECT_ID}}/'")

        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()
        (workspace_dir / "vite.config.ts").write_text("base: '/{{PROJECT_ID}}/'")

        sandbox = DummySandbox(SandboxInfo(project_id="abc123", workspace_dir=str(workspace_dir), port=0))
        sandbox._stamp_vite_config(str(template_dir))

        result = (workspace_dir / "vite.config.ts").read_text()
        assert "abc123" in result
        assert "{{PROJECT_ID}}" not in result

    def test_leaves_other_content_unchanged(self, tmp_path) -> None:  # type: ignore[type-arg]
        template_dir = tmp_path / "template"
        template_dir.mkdir()
        content = "export default { base: '/{{PROJECT_ID}}/', plugins: [] }"
        (template_dir / "vite.config.ts").write_text(content)

        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()
        (workspace_dir / "vite.config.ts").write_text(content)

        sandbox = DummySandbox(SandboxInfo(project_id="proj42", workspace_dir=str(workspace_dir), port=0))
        sandbox._stamp_vite_config(str(template_dir))

        result = (workspace_dir / "vite.config.ts").read_text()
        assert "plugins: []" in result
        assert "proj42" in result
