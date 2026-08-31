"""Tests for versioning orchestration (commit_turn / restore) against a real DB + git."""

from pathlib import Path

import pytest

from flow44.db.events import emit_event, get_versions, subscribe, unsubscribe
from flow44.db.heartbeat import clear_heartbeat
from flow44.services.versioning import service as versioning
from flow44.services.versioning.git import Git, GitError

from .conftest import outer_repo, requires_git

pytestmark = [pytest.mark.asyncio, requires_git]


async def preview(project_id: str, sha: str | None) -> None:
    await versioning.preview_version(project_id, sha or "")


async def restore(project_id: str, sha: str | None) -> None:
    await versioning.restore_version(project_id, sha or "")


async def exit_preview(project_id: str) -> None:
    await versioning.exit_preview(project_id)


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
    # No repo yet: the first commit_turn must init and record the baseline, labeled "Version 0".
    (workspace / "a.txt").write_text("x")
    assert await versioning.commit_turn(project_id) is None  # everything landed in the baseline
    versions = await get_versions(project_id)
    assert len(versions) == 1
    assert versions[0].payload["commit_sha"] == await Git(project_id).head_sha()
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


async def test_begin_turn_refuses_while_detached(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("two")
    await versioning.commit_turn(project_id)

    assert await versioning.begin_turn(project_id) is not None
    await clear_heartbeat(project_id)
    await git.checkout(v0)
    with pytest.raises(versioning.WorkspaceLocked) as excinfo:
        await versioning.begin_turn(project_id)
    assert excinfo.value.payload["code"] == "previewing"


async def test_preview_old_version_detaches(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")
    (workspace / "a.txt").write_text("two")
    v1 = await versioning.commit_turn(project_id)
    (workspace / "a.txt").write_text("three")
    await versioning.commit_turn(project_id)

    await preview(project_id, v1)  # type: ignore[arg-type]

    assert Git(project_id).is_detached()
    assert (workspace / "a.txt").read_text() == "two"


async def test_preview_latest_stays_attached(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")
    (workspace / "a.txt").write_text("two")
    v1 = await versioning.commit_turn(project_id)

    await preview(project_id, v1)  # type: ignore[arg-type]

    assert not Git(project_id).is_detached()


async def test_preview_unknown_sha_raises(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")
    (workspace / "a.txt").write_text("two")
    await versioning.commit_turn(project_id)

    with pytest.raises(versioning.UnknownVersionError):
        await preview(project_id, "deadbeef")


async def test_exit_preview_reattaches(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("two")
    await versioning.commit_turn(project_id)
    await git.checkout(v0)
    assert Git(project_id).is_detached()

    await exit_preview(project_id)

    assert not Git(project_id).is_detached()
    assert (workspace / "a.txt").read_text() == "two"


async def test_restore_resets_git_and_trims_forward_events(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")

    (workspace / "a.txt").write_text("two")
    v1 = await versioning.commit_turn(project_id)
    (workspace / "a.txt").write_text("three")
    await versioning.commit_turn(project_id)
    assert len(await get_versions(project_id)) == 2

    await restore(project_id, v1)  # type: ignore[arg-type]

    remaining = await get_versions(project_id)
    assert [v.payload["commit_sha"] for v in remaining] == [v1]
    assert await Git(project_id).head_sha() == v1
    assert (workspace / "a.txt").read_text() == "two"


async def test_commit_turn_inits_own_repo_when_nested(project_id: str, workspace: Path, tmp_path: Path) -> None:
    # Outer repo around the workspace: a legacy project must still init its own repo.
    outer_head = outer_repo(tmp_path)
    (workspace / "a.txt").write_text("x")

    await versioning.commit_turn(project_id)

    git = Git(project_id)
    assert git.is_repo()
    assert await git.head_sha() != outer_head
    assert (workspace / ".git").exists()
    assert [v.payload["commit_sha"] for v in await get_versions(project_id)] == [await git.head_sha()]


async def test_connect_sync_resets_an_orphaned_preview(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("two")
    await versioning.commit_turn(project_id)

    await git.checkout(v0)
    assert git.is_detached()

    await versioning.broadcast_current_version(project_id, reset_orphaned_preview=True)

    assert not git.is_detached()
    assert (workspace / "a.txt").read_text() == "two"


async def test_connect_sync_leaves_a_live_preview_alone(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("two")
    await versioning.commit_turn(project_id)
    await git.checkout(v0)

    queue = subscribe(project_id)
    try:
        await versioning.broadcast_current_version(project_id, reset_orphaned_preview=False)
    finally:
        unsubscribe(project_id, queue)

    assert git.is_detached()
    assert (workspace / "a.txt").read_text() == "one"
    assert queue.get_nowait()["is_latest"] is False  # the joining tab is told it is mid-preview


async def test_connect_sync_resets_and_broadcasts(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    v0 = await git.init("v0")
    (workspace / "a.txt").write_text("two")
    await versioning.commit_turn(project_id)
    await git.checkout(v0)

    queue = subscribe(project_id)
    try:
        await versioning.broadcast_current_version(project_id, reset_orphaned_preview=True)
    finally:
        unsubscribe(project_id, queue)

    assert not git.is_detached()
    assert queue.get_nowait()["is_latest"] is True


async def test_preview_restore_preview_exit_stays_on_restored_version(project_id: str, workspace: Path) -> None:
    # The reported bug: exiting a later preview resurrected a version the restore had discarded.
    (workspace / "a.txt").write_text("zero")
    await versioning.ensure_repo(project_id)
    git = Git(project_id)
    v0 = await git.head_sha()
    for content in ("one", "two", "three"):
        (workspace / "a.txt").write_text(content)
        await versioning.commit_turn(project_id)
    v2 = (await get_versions(project_id))[2].payload["commit_sha"]

    await preview(project_id, v2)
    await restore(project_id, v2)
    await preview(project_id, v0)
    await exit_preview(project_id)

    assert await git.head_sha() == v2
    assert not git.is_detached()
    assert (workspace / "a.txt").read_text() == "two"
    assert [v.payload["commit_sha"] for v in await get_versions(project_id)][-1] == v2


async def test_restore_keeps_events_when_git_fails(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")
    (workspace / "a.txt").write_text("two")
    v1 = await versioning.commit_turn(project_id)
    await emit_event(project_id, {"type": "version_committed", "commit_sha": "0" * 40}, notify=False)

    with pytest.raises(GitError):
        await restore(project_id, "0" * 40)

    assert len(await get_versions(project_id)) == 2
    assert await Git(project_id).head_sha() == v1


async def test_restore_to_scaffold_version(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("zero")
    await versioning.ensure_repo(project_id)
    v0 = await Git(project_id).head_sha()
    (workspace / "a.txt").write_text("one")
    await versioning.commit_turn(project_id)

    await restore(project_id, v0)

    assert [v.payload["commit_sha"] for v in await get_versions(project_id)] == [v0]
    assert (workspace / "a.txt").read_text() == "zero"


async def test_broadcast_gives_a_legacy_project_its_baseline(
    project_id: str, workspace: Path, tmp_path: Path
) -> None:
    # F-10: head_sha() used to leak the enclosing repo's HEAD, giving legacy projects a false preview banner.
    outer_head = outer_repo(tmp_path)
    (workspace / "a.txt").write_text("x")

    queue = subscribe(project_id)
    try:
        await versioning.broadcast_current_version(project_id, reset_orphaned_preview=False)
    finally:
        unsubscribe(project_id, queue)

    v0 = await Git(project_id).head_sha()
    assert [v.payload["commit_sha"] for v in await get_versions(project_id)] == [v0]
    assert v0 != outer_head
    assert queue.get_nowait()["type"] == "version_committed"
    assert queue.get_nowait() == {"type": "version_preview_active", "commit_sha": v0, "is_latest": True}


async def test_save_version_bootstraps_a_project_with_no_baseline(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("x")

    await versioning.save_version(project_id)

    versions = await get_versions(project_id)
    assert len(versions) == 1
    assert versions[0].payload["commit_sha"] == await Git(project_id).head_sha()


async def test_broadcast_current_version_reports_the_real_head(project_id: str, workspace: Path) -> None:
    # A half-failed version op must still leave the client knowing where git actually is.
    (workspace / "a.txt").write_text("zero")
    await versioning.ensure_repo(project_id)
    v0 = await Git(project_id).head_sha()
    (workspace / "a.txt").write_text("one")
    await versioning.commit_turn(project_id)
    await Git(project_id).checkout(v0)

    queue = subscribe(project_id)
    try:
        await versioning.broadcast_current_version(project_id)
    finally:
        unsubscribe(project_id, queue)

    event = queue.get_nowait()
    assert event == {"type": "version_preview_active", "commit_sha": v0, "is_latest": False}


async def test_preview_refuses_over_a_dirty_tree(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")
    (workspace / "a.txt").write_text("two")
    v1 = await versioning.commit_turn(project_id)
    (workspace / "a.txt").write_text("three")
    await versioning.commit_turn(project_id)
    (workspace / "a.txt").write_text("MANUAL-EDIT")

    with pytest.raises(versioning.WorkspaceLocked) as excinfo:
        await preview(project_id, v1)

    assert excinfo.value.payload["code"] == "dirty_workspace"
    assert excinfo.value.payload["files"] == ["a.txt"]
    assert (workspace / "a.txt").read_text() == "MANUAL-EDIT"
    assert not Git(project_id).is_detached()


async def test_save_version_commits_the_edit_as_its_own_version(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")
    (workspace / "a.txt").write_text("two")
    await versioning.commit_turn(project_id)
    (workspace / "a.txt").write_text("MANUAL-EDIT")

    await versioning.save_version(project_id)

    versions = await get_versions(project_id)
    assert versions[-1].payload["author"] == "user"
    assert versions[-1].payload["files"] == ["a.txt"]
    assert not await Git(project_id).is_dirty()


async def test_save_version_on_a_clean_tree_commits_nothing(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")
    (workspace / "a.txt").write_text("two")
    await versioning.commit_turn(project_id)

    await versioning.save_version(project_id)

    assert len(await get_versions(project_id)) == 1


async def test_discard_edits_removes_modifications_and_untracked_files(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    git = Git(project_id)
    await git.init("v0")
    (workspace / "a.txt").write_text("two")
    await versioning.commit_turn(project_id)
    (workspace / "a.txt").write_text("MANUAL-EDIT")
    (workspace / "scratch.txt").write_text("untracked")

    await versioning.discard_edits(project_id)

    assert (workspace / "a.txt").read_text() == "two"
    assert not (workspace / "scratch.txt").exists()
    assert not await git.is_dirty()
    assert len(await get_versions(project_id)) == 1


async def test_a_saved_edit_stays_out_of_the_next_ai_version(project_id: str, workspace: Path) -> None:
    # The regression: commit_turn used to sweep an uncommitted user edit in as author="ai".
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")
    (workspace / "user.txt").write_text("mine")

    with pytest.raises(versioning.WorkspaceLocked):
        await versioning.begin_turn(project_id)
    await versioning.save_version(project_id)

    (workspace / "ai.txt").write_text("theirs")
    sha = await versioning.commit_turn(project_id)

    versions = await get_versions(project_id)
    assert [v.payload["author"] for v in versions] == ["user", "ai"]
    assert versions[0].payload["files"] == ["user.txt"]
    touched = await Git(project_id)._run("diff", "--name-only", f"{sha}~1", sha)
    assert touched.splitlines() == ["ai.txt"]


async def test_version_op_refused_while_a_run_is_active(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")
    (workspace / "a.txt").write_text("two")
    v1 = await versioning.commit_turn(project_id)

    assert await versioning.begin_turn(project_id) is not None
    with pytest.raises(versioning.WorkspaceLocked) as excinfo:
        await preview(project_id, v1)
    assert excinfo.value.payload["code"] == "run_active"


async def test_needs_writable_passes_on_an_idle_attached_workspace(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    await Git(project_id).init("v0")
    (workspace / "a.txt").write_text("two")

    await versioning.require_writable(project_id)


async def test_ensure_repo_is_idempotent_and_seeds_a_gitignore(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")
    (workspace / "node_modules").mkdir()
    (workspace / "node_modules" / "dep.js").write_text("noise")

    await versioning.ensure_repo(project_id)
    v0 = await Git(project_id).head_sha()
    await versioning.ensure_repo(project_id)

    assert await Git(project_id).head_sha() == v0
    assert len(await get_versions(project_id)) == 1
    tracked = await Git(project_id)._run("ls-files")
    assert not any(f.startswith("node_modules") for f in tracked.splitlines())


async def test_ensure_repo_keeps_an_existing_gitignore(project_id: str, workspace: Path) -> None:
    (workspace / ".gitignore").write_text("mine\n")

    await versioning.ensure_repo(project_id)

    assert (workspace / ".gitignore").read_text() == "mine\n"


async def test_a_failed_op_re_emits_the_real_head(project_id: str, workspace: Path) -> None:
    (workspace / "a.txt").write_text("zero")
    await versioning.ensure_repo(project_id)
    v0 = await Git(project_id).head_sha()
    (workspace / "a.txt").write_text("one")
    await versioning.commit_turn(project_id)
    await Git(project_id).checkout(v0)

    queue = subscribe(project_id)
    try:
        (workspace / "a.txt").write_text("MANUAL-EDIT")
        with pytest.raises(versioning.WorkspaceLocked):
            await preview(project_id, v0)
        assert queue.empty()  # a refusal changed nothing, so there is nothing to resync

        (workspace / "a.txt").write_text("zero")
        await emit_event(project_id, {"type": "version_committed", "commit_sha": "0" * 40}, notify=False)
        with pytest.raises(GitError):
            await restore(project_id, "0" * 40)
    finally:
        unsubscribe(project_id, queue)

    assert queue.get_nowait() == {"type": "version_preview_active", "commit_sha": v0, "is_latest": False}
