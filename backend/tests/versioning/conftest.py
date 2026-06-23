"""Fixtures for versioning tests — real git in a temp workspace, no mocks."""

import os
import shutil

import pytest

from flow44.db.project import create_project
from flow44.sandbox.base import SandboxInfo
from flow44.sandbox.main import PnpmSandboxUnix, PnpmSandboxWindows

git_missing = shutil.which("git") is None
requires_git = pytest.mark.skipif(git_missing, reason="git not installed")


@pytest.fixture
async def sandbox(tmp_path, test_db):  # type: ignore[type-arg,no-untyped-def]
    """A real platform sandbox (exec + filesystem) rooted at a temp workspace, backed by a real project row."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = await create_project("Versioning Test", user_id="test-user")
    info = SandboxInfo(project_id=project.id, workspace_dir=str(workspace), port=0)
    cls = PnpmSandboxWindows if os.name == "nt" else PnpmSandboxUnix
    return cls(info)
