"""Tests for SandboxManager: create, get, destroy, port lifecycle, stamp_vite_config."""

from unittest.mock import patch

import pytest

from flow44.config import settings
from flow44.sandbox.base import SandboxInfo
from flow44.sandbox.manager import SandboxManager, SandboxNotFoundError

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
    async def test_get_unknown_raises(self, manager) -> None:  # type: ignore[type-arg]
        mgr, *_ = manager
        with pytest.raises(SandboxNotFoundError):
            mgr.get_sandbox("nonexistent")

    async def test_create_and_get(self, manager) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, mock_s = manager
        with patch("flow44.sandbox.manager.settings", mock_s):
            sandbox = await mgr.create_sandbox("proj1")
        assert mgr.get_sandbox("proj1") is sandbox

    async def test_get_or_create_idempotent(self, manager) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, mock_s = manager
        with patch("flow44.sandbox.manager.settings", mock_s):
            s1 = await mgr.get_or_create_sandbox("proj1")
            s2 = await mgr.get_or_create_sandbox("proj1")
        assert s1 is s2

    async def test_destroy_removes_sandbox(self, manager) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, mock_s = manager
        with patch("flow44.sandbox.manager.settings", mock_s):
            await mgr.create_sandbox("proj1")
            await mgr.destroy_sandbox("proj1", delete_workspace=False)
        with pytest.raises(SandboxNotFoundError):
            mgr.get_sandbox("proj1")

    async def test_port_freed_after_destroy(self, manager) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, mock_s = manager
        with patch("flow44.sandbox.manager.settings", mock_s):
            sandbox = await mgr.create_sandbox("proj1")
            port = sandbox.port
            assert port not in mgr._available_ports
            await mgr.destroy_sandbox("proj1", delete_workspace=False)
        assert port in mgr._available_ports

    async def test_destroy_nonexistent_no_error(self, manager) -> None:  # type: ignore[type-arg]
        mgr, *_ = manager
        await mgr.destroy_sandbox("ghost", delete_workspace=False)  # must not raise

    async def test_destroy_all(self, manager) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, mock_s = manager
        with patch("flow44.sandbox.manager.settings", mock_s):
            await mgr.create_sandbox("p1")
            await mgr.create_sandbox("p2")
            await mgr.destroy_all(delete_workspaces=False)
        with pytest.raises(SandboxNotFoundError):
            mgr.get_sandbox("p1")
        with pytest.raises(SandboxNotFoundError):
            mgr.get_sandbox("p2")

    async def test_workspace_dir_is_under_base(self, manager) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, mock_s = manager
        with patch("flow44.sandbox.manager.settings", mock_s):
            sandbox = await mgr.create_sandbox("myproject")
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

    def test_replaces_auth_post_message_target(self, tmp_path) -> None:  # type: ignore[type-arg]
        template_dir = tmp_path / "template"
        template_dir.mkdir()
        (template_dir / "vite.config.ts").write_text(
            "'import.meta.env.VITE_AUTH_POST_MESSAGE_TARGET': JSON.stringify('{{AUTH_POST_MESSAGE_TARGET}}'),"
        )

        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()
        (workspace_dir / "vite.config.ts").write_text("")

        sandbox = DummySandbox(SandboxInfo(project_id="proj", workspace_dir=str(workspace_dir), port=0))
        with patch.object(settings, "SANDBOX_AUTH_POST_MESSAGE_TARGET", "https://auth.example.com"):
            sandbox._stamp_vite_config(str(template_dir))

        result = (workspace_dir / "vite.config.ts").read_text()
        assert "https://auth.example.com" in result
        assert "{{AUTH_POST_MESSAGE_TARGET}}" not in result
