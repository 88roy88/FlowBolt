"""Tests for Git — real git operations in a temp workspace."""

import asyncio
from pathlib import Path

import pytest

from flow44.config import settings
from flow44.services.versioning.git import Git, GitError

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


async def test_restore_main_drops_ahead_but_reflog_keeps(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("two")
    v1 = await git.commit_all("two")
    assert v1

    await git.restore_main(v0)
    assert await git.head_sha() == v0
    assert (workspace / "a.txt").read_text() == "one"
    reflog = await git._run("reflog")
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
    subject = await git._run("log", "-1", "--format=%s")
    assert subject == "Version 7"


async def test_restore_main_moves_branch_from_detached_head(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    await git.init("v0")
    (workspace / "a.txt").write_text("two")
    v1 = await git.commit_all("two")
    (workspace / "a.txt").write_text("three")
    await git.commit_all("three")
    assert v1

    await git.checkout(v1)
    await git.restore_main(v1)

    assert await git.head_sha() == v1
    assert await git._run("rev-parse", "main") == v1
    assert not await git.is_detached()
    assert (workspace / "a.txt").read_text() == "two"


async def test_restore_main_from_attached_head(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("two")
    await git.commit_all("two")
    assert v0

    await git.restore_main(v0)

    assert await git.head_sha() == v0
    assert await git._run("rev-parse", "main") == v0
    assert not await git.is_detached()


async def test_run_raises_with_git_stderr(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("x")
    git = Git(project_id)
    await git.init("v0")

    with pytest.raises(GitError) as excinfo:
        await git.checkout("deadbeef")

    assert "deadbeef" in str(excinfo.value)


async def test_checkout_latest_raises_when_main_missing(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("two")
    await git.commit_all("two")
    assert v0

    await git.checkout(v0)
    await git._run("branch", "-D", "main")

    with pytest.raises(GitError):
        await git.checkout_latest()


async def test_restore_main_recreates_branch_when_checkout_would_fail(project_id: str, workspace: Path) -> None:
    # Restore must re-point `main` itself: relying on a prior checkout left main ahead when that checkout failed.
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("two")
    await git.commit_all("two")
    assert v0

    await git.checkout(v0)
    await git._run("branch", "-D", "main")

    await git.restore_main(v0)

    assert await git._run("rev-parse", "main") == v0
    assert not await git.is_detached()


async def test_queries_stay_safe_outside_a_repo(project_id: str, workspace: Path) -> None:
    git = Git(project_id)

    assert await git.is_repo() is False
    assert await git.is_detached() is False


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
