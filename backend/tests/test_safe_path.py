"""Tests for sandbox path traversal prevention."""

from __future__ import annotations

import os

import pytest

from flow44.sandbox.base import Sandbox, SandboxInfo


class _DummySandbox(Sandbox):
    """Minimal sandbox subclass for testing _safe_path."""

    def exec(self, command: str):  # type: ignore[override]
        raise NotImplementedError

    async def start_dev_server(self) -> None:
        raise NotImplementedError

    def create_pty(self):  # type: ignore[override]
        raise NotImplementedError


@pytest.fixture
def sandbox(tmp_path) -> _DummySandbox:  # type: ignore[type-arg]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "src").mkdir()
    (workspace / "src" / "App.tsx").write_text("export default function App() {}")
    info = SandboxInfo(session_id="test", workspace_dir=str(workspace), port=3000)
    return _DummySandbox(info)


class TestSafePath:
    def test_normal_path(self, sandbox: _DummySandbox) -> None:
        result = sandbox._safe_path("src/App.tsx")
        assert result.endswith("src/App.tsx")
        assert os.path.isfile(result)

    def test_leading_slash_stripped(self, sandbox: _DummySandbox) -> None:
        result = sandbox._safe_path("/src/App.tsx")
        assert result.endswith("src/App.tsx")

    def test_dotdot_attack_blocked(self, sandbox: _DummySandbox) -> None:
        with pytest.raises(PermissionError, match="Path traversal"):
            sandbox._safe_path("../../etc/passwd")

    def test_dotdot_in_middle_blocked(self, sandbox: _DummySandbox) -> None:
        with pytest.raises(PermissionError, match="Path traversal"):
            sandbox._safe_path("src/../../etc/passwd")

    def test_absolute_path_resolves_inside_workspace(self, sandbox: _DummySandbox) -> None:
        """Leading slash is stripped, so /etc/passwd becomes etc/passwd inside workspace."""
        result = sandbox._safe_path("/etc/passwd")
        assert sandbox.workspace_dir in result
        assert result.endswith("etc/passwd")

    def test_root_path(self, sandbox: _DummySandbox) -> None:
        result = sandbox._safe_path("/")
        assert result == os.path.realpath(sandbox.workspace_dir)

    def test_empty_path(self, sandbox: _DummySandbox) -> None:
        result = sandbox._safe_path("")
        assert result == os.path.realpath(sandbox.workspace_dir)
