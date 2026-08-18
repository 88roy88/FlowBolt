"""Tests for Git — real git operations in a temp workspace."""

import asyncio
import os

import pytest

from flow44.sandbox.base import SandboxInfo
from flow44.sandbox.main import PnpmSandboxUnix, PnpmSandboxWindows
from flow44.services.versioning.git import Git

from .conftest import requires_git

pytestmark = requires_git


async def test_init_creates_repo_and_baseline(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("index.html", "<h1>v0</h1>")
    git = Git(sandbox)
    sha = await git.init("Version 0 — blank scaffold")
    assert sha
    assert await git.is_repo()
    assert await git.head_sha() == sha


async def test_commit_all_noop_on_clean_tree(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "x")
    git = Git(sandbox)
    await git.init("v0")
    assert await git.commit_all("nothing changed") is None


async def test_commit_all_on_dirty_tree(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "x")
    git = Git(sandbox)
    v0 = await git.init("v0")
    await sandbox.write_file("a.txt", "y")
    v1 = await git.commit_all("change a")
    assert v1 and v1 != v0


async def test_checkout_roundtrip(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "one")
    git = Git(sandbox)
    v0 = await git.init("v0")
    await sandbox.write_file("a.txt", "two")
    await git.commit_all("two")

    await git.checkout(v0)
    assert await sandbox.read_file("a.txt") == "one"
    await git.checkout_latest()
    assert await sandbox.read_file("a.txt") == "two"


async def test_reset_hard_drops_ahead_but_reflog_keeps(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "one")
    git = Git(sandbox)
    v0 = await git.init("v0")
    await sandbox.write_file("a.txt", "two")
    v1 = await git.commit_all("two")
    assert v1

    await git.reset_hard(v0)
    assert await git.head_sha() == v0
    assert await sandbox.read_file("a.txt") == "one"
    _, reflog = await git._run("reflog")
    assert v1[:7] in reflog


async def test_detached_detection(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "1")
    git = Git(sandbox)
    v0 = await git.init("v0")
    await sandbox.write_file("a.txt", "2")
    await git.commit_all("2")

    assert not await git.is_detached()
    await git.checkout(v0)
    assert await git.is_detached()


async def test_commit_message_preserved(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "x")
    git = Git(sandbox)
    await git.init("v0")
    await sandbox.write_file("a.txt", "y")
    await git.commit_all("Version 7")
    _, subject = await git._run("log", "-1", "--format=%s")
    assert subject == "Version 7"


async def test_git_dir_excluded_from_listing(sandbox) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "1")
    git = Git(sandbox)
    await git.init("v0")
    entries = await sandbox.list_files("/")
    assert ".git" not in [e.name for e in entries]


def test_runs_on_a_selector_event_loop(tmp_path) -> None:  # type: ignore[no-untyped-def]
    # uvicorn serves on a selector loop, which has no subprocess support — regression guard.
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    info = SandboxInfo(project_id="selector-loop", workspace_dir=str(workspace), port=0)
    cls = PnpmSandboxWindows if os.name == "nt" else PnpmSandboxUnix
    git = Git(cls(info))

    loop = asyncio.SelectorEventLoop()
    try:
        assert loop.run_until_complete(git.is_repo()) is False
    finally:
        loop.close()
