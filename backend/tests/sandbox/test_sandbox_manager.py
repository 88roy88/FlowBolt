"""Tests for SandboxManager: create, get, destroy, port lifecycle, stamp_vite_config."""

import os
from typing import ClassVar
from unittest.mock import MagicMock, patch

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


class _FakeProcessSandbox(DummySandbox):
    """Sandbox class whose process table is a dict of pid -> (port | None, cmdline)."""

    processes: ClassVar[dict[int, tuple[int | None, str]]] = {}
    killed: ClassVar[list[int]] = []

    @classmethod
    def find_pids_in_port_range(cls, port_start: int, port_end: int) -> list[tuple[int, int]]:
        return [
            (pid, port)
            for pid, (port, _) in cls.processes.items()
            if port is not None and port_start <= port <= port_end
        ]

    @classmethod
    def kill_pid(cls, pid: int) -> None:
        cls.killed.append(pid)

    @classmethod
    def get_pid_cmdline(cls, pid: int) -> str | None:
        entry = cls.processes.get(pid)
        return entry[1] if entry else None


@pytest.fixture
def fake_processes(manager):  # type: ignore[type-arg]
    mgr, workspace_base, _ = manager
    _FakeProcessSandbox.processes = {}
    _FakeProcessSandbox.killed = []
    with patch.object(SandboxManager, "_get_sandbox_class", staticmethod(lambda: _FakeProcessSandbox)):
        yield mgr, workspace_base, _FakeProcessSandbox


@pytest.mark.asyncio
class TestOrphanProcessCleanup:
    async def test_foreign_listener_in_range_is_left_alone(self, fake_processes) -> None:  # type: ignore[type-arg]
        mgr, _, fake = fake_processes
        fake.processes = {
            4242: (19104, r"C:\Program Files\Docker\Docker\resources\com.docker.backend.exe"),
        }
        await mgr.reconcile_workspaces(set())
        assert fake.killed == []

    async def test_workspace_listener_in_range_is_killed(self, fake_processes) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, fake = fake_processes
        vite = os.path.join(workspace_base, "proj1", "node_modules", "vite", "bin", "vite.js")
        fake.processes = {
            100: (19101, f"node {vite} --port 19101"),
            200: (19102, "/usr/bin/some-other-server --port 19102"),
        }
        await mgr.reconcile_workspaces({"proj1"})
        assert fake.killed == [100]

    async def test_pidfile_process_is_killed_and_pidfile_removed(self, fake_processes) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, fake = fake_processes
        workspace_dir = os.path.join(workspace_base, "proj1")
        os.makedirs(workspace_dir)
        pidfile = os.path.join(workspace_dir, ".dev-server.pid")
        with open(pidfile, "w") as f:
            f.write("300")
        # Root shell of the dev server: holds no port itself.
        fake.processes = {300: (None, f"cmd /c cd /d {workspace_dir} && pnpm dev")}

        await mgr.reconcile_workspaces({"proj1"})

        assert fake.killed == [300]
        assert not os.path.exists(pidfile)

    async def test_pidfile_with_reused_pid_is_not_killed(self, fake_processes) -> None:  # type: ignore[type-arg]
        mgr, workspace_base, fake = fake_processes
        workspace_dir = os.path.join(workspace_base, "proj1")
        os.makedirs(workspace_dir)
        pidfile = os.path.join(workspace_dir, ".dev-server.pid")
        with open(pidfile, "w") as f:
            f.write("300")
        fake.processes = {300: (None, "explorer.exe")}

        await mgr.reconcile_workspaces({"proj1"})

        assert fake.killed == []
        assert not os.path.exists(pidfile)


@pytest.mark.asyncio
class TestBackgroundPidfile:
    async def test_register_writes_pidfile_and_stop_removes_it(self, sandbox) -> None:  # type: ignore[type-arg]
        proc = MagicMock(pid=1234, returncode=0)
        log_file = MagicMock()
        sandbox._register_background("dev-server", proc, log_file)

        pidfile = sandbox.get_background_pid_path("dev-server")
        with open(pidfile) as f:
            assert f.read() == "1234"

        await sandbox.stop_background_process("dev-server")
        assert not os.path.exists(pidfile)
