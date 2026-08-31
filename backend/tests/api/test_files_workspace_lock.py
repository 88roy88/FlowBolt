"""The five mutating file endpoints refuse while a run owns the tree or a preview is active."""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from flow44.api.deps import get_project, get_sandbox
from flow44.config import settings
from flow44.main import app
from flow44.services.versioning.git import Git

from .test_files_api import _override_sandbox

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")

client = TestClient(app)

PROJECT_ID = "proj-workspace-lock"

MUTATIONS: list[tuple[str, str, dict[str, Any]]] = [
    ("put", "/file/content", {"json": {"path": "/a.txt", "content": "x"}}),
    ("post", "/file", {"json": {"path": "/new.txt", "content": "x"}}),
    ("patch", "/file", {"json": {"old_path": "/a.txt", "new_path": "/b.txt"}}),
    ("delete", "/file?path=/a.txt", {}),
    ("post", "/file/upload?path=/bin.dat", {"content": b"\x00"}),
]


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Git]:
    monkeypatch.setattr(settings, "WORKSPACE_BASE_DIR", str(tmp_path))
    root = tmp_path / PROJECT_ID
    root.mkdir()
    (root / "a.txt").write_text("one")
    git = Git(PROJECT_ID)
    asyncio.run(git.init("v0"))  # already a repo, so the guard never has to reach the DB to make one

    project = MagicMock()
    project.id = PROJECT_ID
    app.dependency_overrides[get_sandbox] = lambda project_id: _override_sandbox(root)
    app.dependency_overrides[get_project] = lambda: project
    yield git
    app.dependency_overrides.pop(get_sandbox, None)
    app.dependency_overrides.pop(get_project, None)


def _mutate(method: str, path: str, kwargs: dict[str, Any], *, run_active: bool = False) -> Any:
    with patch("flow44.services.versioning.service.is_run_active", AsyncMock(return_value=run_active)):
        return client.request(method.upper(), f"/api/files/{PROJECT_ID}{path}", **kwargs)


@pytest.mark.parametrize(("method", "path", "kwargs"), MUTATIONS)
def test_refused_while_a_run_is_active(repo: Git, method: str, path: str, kwargs: dict[str, Any]) -> None:
    response = _mutate(method, path, kwargs, run_active=True)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "run_active"


@pytest.mark.parametrize(("method", "path", "kwargs"), MUTATIONS)
def test_refused_while_previewing(repo: Git, method: str, path: str, kwargs: dict[str, Any]) -> None:
    asyncio.run(repo.checkout(asyncio.run(repo.head_sha())))

    response = _mutate(method, path, kwargs)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "previewing"


def test_allowed_on_an_idle_attached_workspace(repo: Git) -> None:
    response = _mutate("put", "/file/content", {"json": {"path": "/a.txt", "content": "two"}})

    assert response.status_code == 200
    assert (Path(repo.workspace_dir) / "a.txt").read_text() == "two"
