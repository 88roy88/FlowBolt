import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from flow44.config import settings
from flow44.db.project import create_project
from flow44.services.versioning import service as versioning
from flow44.services.versioning.git import Git

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


@dataclass(frozen=True)
class VersionChain:
    git: Git
    workspace: Path
    shas: tuple[str, str, str]


@pytest.fixture
async def repo(project_id: str, workspace: Path) -> Git:
    (workspace / "a.txt").write_text("zero")
    git = Git(project_id)
    await git.init("v0")
    return git


@pytest.fixture
async def version_chain(project_id: str, workspace: Path) -> VersionChain:
    (workspace / "a.txt").write_text("zero")
    await versioning.ensure_repo(project_id)
    git = Git(project_id)
    v0 = await git.head_sha()
    shas = [v0]
    for content in ("one", "two"):
        (workspace / "a.txt").write_text(content)
        sha = await versioning.commit_turn(project_id)
        assert sha
        shas.append(sha)
    return VersionChain(git, workspace, (shas[0], shas[1], shas[2]))


@pytest.fixture
async def dirty_chain(version_chain: VersionChain) -> VersionChain:
    (version_chain.workspace / "a.txt").write_text("MANUAL-EDIT")
    (version_chain.workspace / "scratch.txt").write_text("untracked")
    return version_chain
