"""Fixtures for versioning tests — real git in a temp workspace, no mocks."""

import shutil
import subprocess
from pathlib import Path

import pytest

from flow44.config import settings
from flow44.db.project import create_project

git_missing = shutil.which("git") is None
requires_git = pytest.mark.skipif(git_missing, reason="git not installed")


def git_out(root: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)  # noqa: S607
    return done.stdout.strip()


def outer_repo(root: Path) -> str:
    git_out(root, "init")
    (root / "sentinel.txt").write_text("outer")
    git_out(root, "add", "-A")
    git_out(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "outer")
    return git_out(root, "rev-parse", "HEAD")


@pytest.fixture
async def project_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_db) -> str:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "WORKSPACE_BASE_DIR", str(tmp_path))
    project = await create_project("Versioning Test", user_id="test-user")
    (tmp_path / project.id).mkdir()
    return project.id


@pytest.fixture
def workspace(tmp_path: Path, project_id: str) -> Path:
    return tmp_path / project_id
