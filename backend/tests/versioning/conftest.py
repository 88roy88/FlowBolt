"""Fixtures for versioning tests — real git in a temp workspace, no mocks."""

import shutil
from pathlib import Path

import pytest

from flow44.config import settings
from flow44.db.project import create_project

git_missing = shutil.which("git") is None
requires_git = pytest.mark.skipif(git_missing, reason="git not installed")


@pytest.fixture
async def project_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_db) -> str:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "WORKSPACE_BASE_DIR", str(tmp_path))
    project = await create_project("Versioning Test", user_id="test-user")
    (tmp_path / project.id).mkdir()
    return project.id


@pytest.fixture
def workspace(tmp_path: Path, project_id: str) -> Path:
    return tmp_path / project_id
