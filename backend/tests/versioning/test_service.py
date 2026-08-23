"""Tests for versioning orchestration (commit_turn / restore) against a real DB + git."""

import subprocess
from pathlib import Path

import pytest

from flow44.db.events import emit_event, get_versions, subscribe, unsubscribe
from flow44.services.versioning import service as versioning
from flow44.services.versioning.git import Git, GitError

from .conftest import requires_git

pytestmark = [pytest.mark.asyncio, requires_git]


async def test_commit_turn_emits_version_event(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("x")
    await Git(project_id).init("v0")  # repo exists (1 commit), no event yet

    (workspace / "a.txt").write_text("y")
    sha = await versioning.commit_turn(project_id)

    versions = await get_versions(project_id)
    assert sha
    assert len(versions) == 1
    assert versions[0].payload["commit_sha"] == sha
    assert "turn_summary" not in versions[0].payload


async def test_commit_turn_noop_on_clean_tree(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("x")
    await Git(project_id).init("v0")

    assert await versioning.commit_turn(project_id) is None
    assert await get_versions(project_id) == []


async def test_commit_turn_initializes_legacy_project(project_id: str, workspace: Path) -> None:
    # No repo yet: the first commit_turn must init and still record a version, labeled "Version 0".
    (workspace / "a.txt").write_text("x")
    sha = await versioning.commit_turn(project_id)
    assert sha
    versions = await get_versions(project_id)
    assert len(versions) == 1
    assert versions[0].payload["commit_sha"] == sha
    subject = await Git(project_id)._run("log", "-1", "--format=%s")
    assert subject == versioning._SCAFFOLD_MESSAGE


async def test_commit_turn_refuses_while_detached(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("x")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("y")
    await versioning.commit_turn(project_id)

    await git.checkout(v0)
    (workspace / "a.txt").write_text("z")
    assert await versioning.commit_turn(project_id) is None
    assert len(await get_versions(project_id)) == 1


async def test_is_previewing_tracks_detached_state(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("two")
    await versioning.commit_turn(project_id)

    assert not await versioning.is_previewing(project_id)
    await git.checkout(v0)
    assert await versioning.is_previewing(project_id)
    await git.checkout_latest()
    assert not await versioning.is_previewing(project_id)


async def test_preview_old_version_detaches(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")
    (workspace / "a.txt").write_text("two")
    v1 = await versioning.commit_turn(project_id)
    (workspace / "a.txt").write_text("three")
    await versioning.commit_turn(project_id)

    await versioning.preview_version(project_id, v1)  # type: ignore[arg-type]

    assert await versioning.is_previewing(project_id)
    assert (workspace / "a.txt").read_text() == "two"


async def test_preview_latest_stays_attached(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")
    (workspace / "a.txt").write_text("two")
    v1 = await versioning.commit_turn(project_id)

    await versioning.preview_version(project_id, v1)  # type: ignore[arg-type]

    assert not await versioning.is_previewing(project_id)


async def test_preview_unknown_sha_raises(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")
    (workspace / "a.txt").write_text("two")
    await versioning.commit_turn(project_id)

    with pytest.raises(versioning.UnknownVersionError):
        await versioning.preview_version(project_id, "deadbeef")


async def test_exit_preview_reattaches(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("two")
    await versioning.commit_turn(project_id)
    await git.checkout(v0)
    assert await versioning.is_previewing(project_id)

    await versioning.exit_preview(project_id)

    assert not await versioning.is_previewing(project_id)
    assert (workspace / "a.txt").read_text() == "two"


async def test_restore_resets_git_and_trims_forward_events(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")

    (workspace / "a.txt").write_text("two")
    v1 = await versioning.commit_turn(project_id)
    (workspace / "a.txt").write_text("three")
    await versioning.commit_turn(project_id)
    assert len(await get_versions(project_id)) == 2

    await versioning.restore_version(project_id, v1)  # type: ignore[arg-type]

    remaining = await get_versions(project_id)
    assert [v.payload["commit_sha"] for v in remaining] == [v1]
    assert await Git(project_id).head_sha() == v1
    assert (workspace / "a.txt").read_text() == "two"


async def test_commit_turn_inits_own_repo_when_nested(project_id: str, workspace: Path, tmp_path: Path) -> None:
    # Outer repo around the workspace: a legacy project must still init its own repo.
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)  # noqa: S607
    (workspace / "a.txt").write_text("x")

    sha = await versioning.commit_turn(project_id)

    assert sha
    git = Git(project_id)
    assert await git.is_repo()
    assert await git.head_sha() == sha
    assert (workspace / ".git").exists()
    assert len(await get_versions(project_id)) == 1


async def test_ensure_at_latest_reattaches_when_detached(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("two")
    await versioning.commit_turn(project_id)

    await git.checkout(v0)
    assert await git.is_detached()

    await versioning.ensure_at_latest(project_id)

    assert not await git.is_detached()
    assert (workspace / "a.txt").read_text() == "two"


async def test_preview_restore_preview_exit_stays_on_restored_version(project_id: str, workspace: Path) -> None:
    # The reported bug: exiting a later preview resurrected a version the restore had discarded.
    (workspace / "a.txt").write_text("zero")
    await versioning.init_scaffold_version(project_id)
    git = Git(project_id)
    v0 = await git.head_sha()
    for content in ("one", "two", "three"):
        (workspace / "a.txt").write_text(content)
        await versioning.commit_turn(project_id)
    v2 = (await get_versions(project_id))[2].payload["commit_sha"]

    await versioning.preview_version(project_id, v2)
    await versioning.restore_version(project_id, v2)
    await versioning.preview_version(project_id, v0)
    await versioning.exit_preview(project_id)

    assert await git.head_sha() == v2
    assert not await git.is_detached()
    assert (workspace / "a.txt").read_text() == "two"
    assert [v.payload["commit_sha"] for v in await get_versions(project_id)][-1] == v2


async def test_restore_keeps_events_when_git_fails(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")
    (workspace / "a.txt").write_text("two")
    v1 = await versioning.commit_turn(project_id)
    await emit_event(project_id, {"type": "version_committed", "commit_sha": "0" * 40}, notify=False)

    with pytest.raises(GitError):
        await versioning.restore_version(project_id, "0" * 40)

    assert len(await get_versions(project_id)) == 2
    assert await Git(project_id).head_sha() == v1


async def test_restore_to_scaffold_version(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("zero")
    await versioning.init_scaffold_version(project_id)
    v0 = await Git(project_id).head_sha()
    (workspace / "a.txt").write_text("one")
    await versioning.commit_turn(project_id)

    await versioning.restore_version(project_id, v0)

    assert [v.payload["commit_sha"] for v in await get_versions(project_id)] == [v0]
    assert (workspace / "a.txt").read_text() == "zero"


async def test_emit_preview_state_reports_the_real_head(project_id: str, workspace: Path) -> None:
    # A half-failed version op must still leave the client knowing where git actually is.
    (workspace / "a.txt").write_text("zero")
    await versioning.init_scaffold_version(project_id)
    v0 = await Git(project_id).head_sha()
    (workspace / "a.txt").write_text("one")
    await versioning.commit_turn(project_id)
    await Git(project_id).checkout(v0)

    queue = subscribe(project_id)
    try:
        await versioning.emit_preview_state(project_id)
    finally:
        unsubscribe(project_id, queue)

    event = queue.get_nowait()
    assert event == {"type": "version_preview_active", "commit_sha": v0, "is_latest": False}
