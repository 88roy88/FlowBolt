"""Tests for versioning orchestration (commit_turn / restore) against a real DB + git."""

import subprocess

import pytest

from flow44.db.events import get_versions
from flow44.services.versioning import service as versioning
from flow44.services.versioning.git_service import GitService

from .conftest import requires_git

pytestmark = [pytest.mark.asyncio, requires_git]


async def _commit_turn(sandbox) -> str | None:  # type: ignore[no-untyped-def]
    return await versioning.commit_turn(sandbox, sandbox.project_id)


async def test_commit_turn_emits_version_event(sandbox, test_db) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "x")
    await GitService(sandbox).init("v0")  # repo exists (1 commit), no event yet

    await sandbox.write_file("a.txt", "y")
    sha = await _commit_turn(sandbox)

    versions = await get_versions(sandbox.project_id)
    assert sha
    assert len(versions) == 1
    assert versions[0].payload["commit_sha"] == sha
    assert "turn_summary" not in versions[0].payload
    # commit count before this commit was 1 (the v0 baseline) -> "Version 1".
    assert await GitService(sandbox)._run("log -1 --format=%s") == "Version 1"


async def test_commit_turn_noop_on_clean_tree(sandbox, test_db) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "x")
    await GitService(sandbox).init("v0")

    assert await _commit_turn(sandbox) is None
    assert await get_versions(sandbox.project_id) == []


async def test_commit_turn_initializes_legacy_project(sandbox, test_db) -> None:  # type: ignore[no-untyped-def]
    # No repo yet: the first commit_turn must init and still record a version, labeled "Version 0".
    await sandbox.write_file("a.txt", "x")
    sha = await _commit_turn(sandbox)
    assert sha
    versions = await get_versions(sandbox.project_id)
    assert len(versions) == 1
    assert versions[0].payload["commit_sha"] == sha
    assert await GitService(sandbox)._run("log -1 --format=%s") == "Version 0"


async def test_commit_turn_refuses_while_detached(sandbox, test_db) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "x")
    git = GitService(sandbox)
    v0 = await git.init("v0")
    await sandbox.write_file("a.txt", "y")
    await _commit_turn(sandbox)

    await git.checkout(v0)
    await sandbox.write_file("a.txt", "z")
    assert await _commit_turn(sandbox) is None
    assert len(await get_versions(sandbox.project_id)) == 1


async def test_is_previewing_tracks_detached_state(sandbox, test_db) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "one")
    git = GitService(sandbox)
    v0 = await git.init("v0")
    await sandbox.write_file("a.txt", "two")
    await _commit_turn(sandbox)

    assert not await versioning.is_previewing(sandbox, sandbox.project_id)
    await git.checkout(v0)
    assert await versioning.is_previewing(sandbox, sandbox.project_id)
    await git.checkout_latest()
    assert not await versioning.is_previewing(sandbox, sandbox.project_id)


async def test_preview_old_version_detaches(sandbox, test_db) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "one")
    await GitService(sandbox).init("v0")
    await sandbox.write_file("a.txt", "two")
    v1 = await _commit_turn(sandbox)
    await sandbox.write_file("a.txt", "three")
    await _commit_turn(sandbox)

    await versioning.preview_version(sandbox, sandbox.project_id, v1)  # type: ignore[arg-type]

    assert await versioning.is_previewing(sandbox, sandbox.project_id)
    assert await sandbox.read_file("a.txt") == "two"


async def test_preview_latest_stays_attached(sandbox, test_db) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "one")
    await GitService(sandbox).init("v0")
    await sandbox.write_file("a.txt", "two")
    v1 = await _commit_turn(sandbox)

    await versioning.preview_version(sandbox, sandbox.project_id, v1)  # type: ignore[arg-type]

    assert not await versioning.is_previewing(sandbox, sandbox.project_id)


async def test_preview_unknown_sha_raises(sandbox, test_db) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "one")
    await GitService(sandbox).init("v0")
    await sandbox.write_file("a.txt", "two")
    await _commit_turn(sandbox)

    with pytest.raises(versioning.UnknownVersionError):
        await versioning.preview_version(sandbox, sandbox.project_id, "deadbeef")


async def test_exit_preview_reattaches(sandbox, test_db) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "one")
    git = GitService(sandbox)
    v0 = await git.init("v0")
    await sandbox.write_file("a.txt", "two")
    await _commit_turn(sandbox)
    await git.checkout(v0)
    assert await versioning.is_previewing(sandbox, sandbox.project_id)

    await versioning.exit_preview(sandbox, sandbox.project_id)

    assert not await versioning.is_previewing(sandbox, sandbox.project_id)
    assert await sandbox.read_file("a.txt") == "two"


async def test_restore_resets_git_and_trims_forward_events(sandbox, test_db) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "one")
    await GitService(sandbox).init("v0")

    await sandbox.write_file("a.txt", "two")
    v1 = await _commit_turn(sandbox)
    await sandbox.write_file("a.txt", "three")
    await _commit_turn(sandbox)
    assert len(await get_versions(sandbox.project_id)) == 2

    await versioning.restore_version(sandbox, sandbox.project_id, v1)  # type: ignore[arg-type]

    remaining = await get_versions(sandbox.project_id)
    assert [v.payload["commit_sha"] for v in remaining] == [v1]
    assert await GitService(sandbox).head_sha() == v1
    assert await sandbox.read_file("a.txt") == "two"


async def test_commit_turn_inits_own_repo_when_nested(sandbox, tmp_path, test_db) -> None:  # type: ignore[no-untyped-def]
    # Outer repo around the workspace: a legacy project must still init its own repo.
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)  # noqa: S607
    await sandbox.write_file("a.txt", "x")

    sha = await _commit_turn(sandbox)

    assert sha
    git = GitService(sandbox)
    assert await git.is_repo()
    assert await git.head_sha() == sha
    assert (tmp_path / "workspace" / ".git").exists()
    assert len(await get_versions(sandbox.project_id)) == 1


async def test_ensure_at_latest_reattaches_when_detached(sandbox, test_db) -> None:  # type: ignore[no-untyped-def]
    await sandbox.write_file("a.txt", "one")
    git = GitService(sandbox)
    v0 = await git.init("v0")
    await sandbox.write_file("a.txt", "two")
    await _commit_turn(sandbox)

    await git.checkout(v0)
    assert await git.current_is_detached()

    await versioning.ensure_at_latest(sandbox, sandbox.project_id)

    assert not await git.current_is_detached()
    assert await sandbox.read_file("a.txt") == "two"
