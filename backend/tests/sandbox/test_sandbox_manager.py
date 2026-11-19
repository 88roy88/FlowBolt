"""Tests for SandboxManager: create, get, destroy, port lifecycle, workspace setup, cleanup, stamp_vite_config."""

import asyncio
import contextlib
import os
import time
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from flow44.config import settings
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
        with patch("flow44.sandbox.base.settings", mock_s):
            yield mgr, workspace_base, mock_s


def _scaffold(project_id: str, workspace_base: str) -> None:
    workspace = os.path.join(workspace_base, project_id)
    os.makedirs(workspace, exist_ok=True)
    with open(os.path.join(workspace, "package.json"), "w") as f:
        f.write("{}")


@contextlib.asynccontextmanager
async def _no_lock(*_args: object) -> AsyncIterator[None]:
    yield


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
        _scaffold("proj1", workspace_base)
        with patch("flow44.sandbox.manager.settings", mock_s), patch.object(mgr, "start_dev_server", AsyncMock()):
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


@pytest.fixture
def setup_deps(manager):  # type: ignore[no-untyped-def]
    """Stubs everything workspace setup touches outside the manager; scaffold just writes package.json."""
    mgr, workspace_base, mock_s = manager
    calls: list[str] = []

    async def scaffold(self, template_dir: str) -> None:  # type: ignore[no-untyped-def]
        calls.append("scaffold")
        _scaffold(self.project_id, workspace_base)

    async def ensure_repo(project_id: str) -> None:
        calls.append("ensure_repo")

    async def start_dev_server(sandbox) -> None:  # type: ignore[no-untyped-def]
        calls.append("start_dev_server")

    emit = AsyncMock()
    with (
        patch("flow44.sandbox.manager.settings", mock_s),
        patch("flow44.sandbox.manager.advisory_lock", _no_lock),
        patch("flow44.sandbox.manager.versioning.ensure_repo", ensure_repo),
        patch("flow44.sandbox.manager.emit_event", emit),
        patch("flow44.sandbox.pnpm_mixin.PnpmMixin.scaffold", scaffold),
        patch.object(mgr, "start_dev_server", start_dev_server),
    ):
        yield mgr, workspace_base, calls, emit


@pytest.mark.asyncio
class TestWorkspaceSetup:
    async def test_new_project_is_set_up_in_background(self, setup_deps) -> None:  # type: ignore[no-untyped-def]
        mgr, _, calls, _ = setup_deps
        await mgr.wake_sandbox("proj1")
        assert calls == []  # wake returned before setup ran
        await mgr._setup_tasks["proj1"]
        assert calls == ["scaffold", "ensure_repo", "start_dev_server"]

    async def test_wake_during_setup_does_not_start_twice(self, setup_deps) -> None:  # type: ignore[no-untyped-def]
        mgr, _, calls, _ = setup_deps
        await mgr.wake_sandbox("proj1")
        task = mgr._setup_tasks["proj1"]
        await mgr.wake_sandbox("proj1")
        await task
        assert calls == ["scaffold", "ensure_repo", "start_dev_server"]
        assert "proj1" not in mgr._setup_tasks

    async def test_scaffolded_project_starts_dev_server_directly(self, setup_deps) -> None:  # type: ignore[no-untyped-def]
        mgr, workspace_base, calls, _ = setup_deps
        _scaffold("proj1", workspace_base)
        await mgr.wake_sandbox("proj1")
        assert calls == ["start_dev_server"]
        assert "proj1" not in mgr._setup_tasks

    async def test_setup_failure_is_reported(self, setup_deps) -> None:  # type: ignore[no-untyped-def]
        mgr, _, _, emit = setup_deps
        with patch("flow44.sandbox.pnpm_mixin.PnpmMixin.scaffold", AsyncMock(side_effect=RuntimeError("boom"))):
            await mgr.wake_sandbox("proj1")
            await mgr._setup_tasks["proj1"]
        emit.assert_awaited_once_with("proj1", {"type": "error", "message": "Project setup failed"})

    async def test_suspend_cancels_setup(self, setup_deps) -> None:  # type: ignore[no-untyped-def]
        mgr, _, calls, _ = setup_deps
        started = asyncio.Event()

        async def slow_scaffold(self, template_dir: str) -> None:  # type: ignore[no-untyped-def]
            started.set()
            await asyncio.sleep(60)

        with patch("flow44.sandbox.pnpm_mixin.PnpmMixin.scaffold", slow_scaffold):
            await mgr.wake_sandbox("proj1")
            task = mgr._setup_tasks["proj1"]
            await started.wait()
            await mgr.suspend_sandbox("proj1")
            with contextlib.suppress(asyncio.CancelledError):
                await task
        assert task.cancelled()
        assert calls == []


class TestOrphanWorkspaceCleanup:
    def test_deletes_only_old_orphans(self, manager) -> None:  # type: ignore[no-untyped-def]
        mgr, workspace_base, mock_s = manager
        for name in ("live", "old-orphan", "new-orphan"):
            _scaffold(name, workspace_base)
        old = time.time() - 3600
        for name in ("live", "old-orphan"):
            os.utime(os.path.join(workspace_base, name), (old, old))

        with patch("flow44.sandbox.manager.settings", mock_s):
            mgr._delete_orphan_workspaces({"live"})

        assert sorted(os.listdir(workspace_base)) == ["live", "new-orphan"]


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
