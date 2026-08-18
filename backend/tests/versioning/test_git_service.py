"""Tests for GitService — real git operations in a temp workspace."""

import pytest

from flow44.services.versioning.git_service import GitService

from .conftest import requires_git

pytestmark = [pytest.mark.asyncio, requires_git]


async def test_init_creates_repo_and_baseline(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("index.html", "<h1>v0</h1>")
    git = GitService(sandbox)
    sha = await git.init("Version 0 — blank scaffold")
    assert sha
    assert await git.is_repo()
    assert await git.head_sha() == sha


async def test_commit_all_noop_on_clean_tree(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "x")
    git = GitService(sandbox)
    await git.init("v0")
    assert await git.commit_all("nothing changed") is None


async def test_commit_all_on_dirty_tree(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "x")
    git = GitService(sandbox)
    v0 = await git.init("v0")
    await sandbox.write_file("a.txt", "y")
    v1 = await git.commit_all("change a")
    assert v1 and v1 != v0


async def test_commit_count_grows_with_history(sandbox) -> None:  # type: ignore[no-untyped-def]
    git = GitService(sandbox)
    assert await git.commit_count() == 0  # unborn repo
    await sandbox.write_file("a.txt", "x")
    await git.init("v0")
    assert await git.commit_count() == 1
    await sandbox.write_file("a.txt", "y")
    await git.commit_all("v1")
    assert await git.commit_count() == 2


async def test_checkout_roundtrip(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "one")
    git = GitService(sandbox)
    v0 = await git.init("v0")
    await sandbox.write_file("a.txt", "two")
    await git.commit_all("two")

    await git.checkout(v0)
    assert await sandbox.read_file("a.txt") == "one"
    await git.checkout_latest()
    assert await sandbox.read_file("a.txt") == "two"


async def test_reset_hard_drops_ahead_but_reflog_keeps(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "one")
    git = GitService(sandbox)
    v0 = await git.init("v0")
    await sandbox.write_file("a.txt", "two")
    v1 = await git.commit_all("two")
    assert v1

    await git.reset_hard(v0)
    assert await git.head_sha() == v0
    assert await sandbox.read_file("a.txt") == "one"
    reflog = await git._run("reflog")
    assert v1[:7] in reflog


async def test_detached_detection(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "1")
    git = GitService(sandbox)
    v0 = await git.init("v0")
    await sandbox.write_file("a.txt", "2")
    await git.commit_all("2")

    assert not await git.current_is_detached()
    await git.checkout(v0)
    assert await git.current_is_detached()


async def test_commit_message_preserved(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "x")
    git = GitService(sandbox)
    await git.init("v0")
    await sandbox.write_file("a.txt", "y")
    await git.commit_all("Version 7")
    subject = await git._run("log -1 --format=%s")
    assert subject == "Version 7"


async def test_git_dir_excluded_from_listing(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "1")
    git = GitService(sandbox)
    await git.init("v0")
    entries = await sandbox.list_files("/")
    assert ".git" not in [e.name for e in entries]
