import shutil
import subprocess
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from flow44.api.deps import get_project, get_sandbox
from flow44.config import settings
from flow44.db.events import emit_event
from flow44.db.project import create_project
from flow44.db.project_data_source import DataSourceContext, update_project_data_sources
from flow44.main import app
from flow44.sandbox.base import SandboxInfo
from flow44.services.versioning import service as versioning
from flow44.services.versioning.git import Git

from ..api.test_files_api import APITestSandbox

git_missing = shutil.which("git") is None
requires_git = pytest.mark.skipif(git_missing, reason="git not installed")

DS_MODULE = "src/dataSources/Sales.ts"


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


@pytest.fixture
def overrides(project_id: str, workspace: Path) -> Iterator[None]:
    project = MagicMock()
    project.id = project_id
    sandbox = APITestSandbox(SandboxInfo(project_id=project_id, workspace_dir=str(workspace), port=0))
    app.dependency_overrides[get_project] = lambda: project
    app.dependency_overrides[get_sandbox] = lambda: sandbox
    yield
    app.dependency_overrides.pop(get_project, None)
    app.dependency_overrides.pop(get_sandbox, None)


@pytest.fixture
async def data_sources_client(overrides: None) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        yield http


@pytest.fixture
async def data_sources_url(project_id: str, workspace: Path) -> str:
    (workspace / "src/dataSources").mkdir(parents=True)
    (workspace / DS_MODULE).write_text("export {}")
    (workspace / "src/dataSources/Sales.docs.md").write_text("docs")
    await versioning.ensure_repo(project_id)
    await update_project_data_sources(
        project_id, [DataSourceContext(data_source_id="12", data_source_name="Sales", sanitized_name="Sales")]
    )
    await emit_event(project_id, {"type": "action_complete"})
    return f"/api/projects/{project_id}/data-sources"
