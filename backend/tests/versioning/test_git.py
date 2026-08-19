"""Tests for Git — real git operations in a temp workspace."""

import asyncio
from pathlib import Path

import pytest

from flow44.config import settings
from flow44.services.versioning.git import Git

from .conftest import requires_git

pytestmark = requires_git


async def test_init_creates_repo_and_baseline(project_id: str, workspace: Path) -> None:
    (workspace / "index.html").write_text("<h1>v0</h1>")
    git = Git(project_id)
    sha = await git.init("Version 0 — blank scaffold")
    assert sha
    assert await git.is_repo()
    assert await git.head_sha() == sha


async def test_commit_all_noop_on_clean_tree(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("x")
    git = Git(project_id)
    await git.init("v0")
    assert await git.commit_all("nothing changed") is None


async def test_commit_all_on_dirty_tree(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("x")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("y")
    v1 = await git.commit_all("change a")
    assert v1 and v1 != v0


async def test_checkout_roundtrip(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("two")
    await git.commit_all("two")

    await git.checkout(v0)
    assert (workspace / "a.txt").read_text() == "one"
    await git.checkout_latest()
    assert (workspace / "a.txt").read_text() == "two"


async def test_reset_hard_drops_ahead_but_reflog_keeps(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("two")
    v1 = await git.commit_all("two")
    assert v1

    await git.reset_hard(v0)
    assert await git.head_sha() == v0
    assert (workspace / "a.txt").read_text() == "one"
    _, reflog = await git._run("reflog")
    assert v1[:7] in reflog


async def test_detached_detection(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("1")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("2")
    await git.commit_all("2")

    assert not await git.is_detached()
    await git.checkout(v0)
    assert await git.is_detached()


async def test_commit_message_preserved(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("x")
    git = Git(project_id)
    await git.init("v0")
    (workspace / "a.txt").write_text("y")
    await git.commit_all("Version 7")
    _, subject = await git._run("log", "-1", "--format=%s")
    assert subject == "Version 7"


def test_runs_on_a_selector_event_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # uvicorn serves on a selector loop, which has no subprocess support — regression guard.
    monkeypatch.setattr(settings, "WORKSPACE_BASE_DIR", str(tmp_path))
    (tmp_path / "selector-loop").mkdir()
    git = Git("selector-loop")

    loop = asyncio.SelectorEventLoop()
    try:
        assert loop.run_until_complete(git.is_repo()) is False
    finally:
        loop.close()
