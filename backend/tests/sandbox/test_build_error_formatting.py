"""Tests for PnpmMixin._format_build_errors workspace-root stripping."""

from pathlib import Path

from flow44.sandbox.base import SandboxInfo
from flow44.sandbox.main import PnpmSandboxNamespace, PnpmSandboxUnix


def _unix(tmp_path: Path) -> PnpmSandboxUnix:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return PnpmSandboxUnix(SandboxInfo(project_id="p", workspace_dir=str(workspace), port=0))


def test_strips_host_workspace_root(tmp_path: Path) -> None:
    sandbox = _unix(tmp_path)

    raw = f"{sandbox.workspace_dir}/src/App.tsx(3,1): error TS1005"
    assert sandbox._format_build_errors(raw) == "src/App.tsx(3,1): error TS1005"


def test_strips_namespaced_mount_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sandbox = PnpmSandboxNamespace(SandboxInfo(project_id="p", workspace_dir=str(workspace), port=0))

    raw = "/home/project/src/App.tsx(3,1): error TS1005"
    assert sandbox._format_build_errors(raw) == "src/App.tsx(3,1): error TS1005"


def test_leaves_relative_paths_untouched(tmp_path: Path) -> None:
    sandbox = _unix(tmp_path)

    raw = "src/App.tsx(3,1): error TS1005"
    assert sandbox._format_build_errors(raw) == raw
