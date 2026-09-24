from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path

import pytest
from sqlalchemy import func, select

from flow44.config import settings
from flow44.db import database
from flow44.db.chat import ChatMessage, ChatRole, get_messages
from flow44.db.events import emit_event, get_versions, subscribe, unsubscribe
from flow44.db.heartbeat import clear_heartbeat
from flow44.db.locks import LockNamespace
from flow44.services.maintenance.template_sync import sync_protected_template_files
from flow44.services.versioning import service as versioning
from flow44.services.versioning.git import Git, GitError

from .conftest import VersionChain, outer_repo, requires_git

pytestmark = [pytest.mark.asyncio, requires_git]

VersionOperation = Callable[[str, str], Awaitable[None]]


async def _preview(project_id: str, sha: str) -> None:
    await versioning.preview_version(project_id, sha)


async def _restore(project_id: str, sha: str) -> None:
    await versioning.restore_version(project_id, sha)


async def test_commit_turn_records_an_ai_version(project_id: str, repo: Git, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one")

    sha = await versioning.commit_turn(project_id)

    versions = await get_versions(project_id)
    assert sha
    assert len(versions) == 1
    assert versions[0].payload == {
        "type": "version_committed",
        "commit_sha": sha,
        "author": "ai",
        "_ts": versions[0].payload["_ts"],
    }


@pytest.mark.parametrize(("operation", "target_index"), [(_preview, 0), (_preview, 2)])
async def test_preview_selects_the_requested_tree(
    project_id: str, version_chain: VersionChain, operation: VersionOperation, target_index: int
) -> None:
    await operation(project_id, version_chain.shas[target_index])

    assert await version_chain.git.head_sha() == version_chain.shas[target_index]
    assert version_chain.git.is_detached() is (target_index != 2)
    assert (version_chain.workspace / "a.txt").read_text() == ("zero" if target_index == 0 else "two")


@pytest.mark.parametrize("operation", [_preview, _restore])
async def test_version_operations_reject_unknown_shas(
    project_id: str, version_chain: VersionChain, operation: VersionOperation
) -> None:
    with pytest.raises(versioning.UnknownVersionError):
        await operation(project_id, "deadbeef")

    assert await version_chain.git.head_sha() == version_chain.shas[2]


@pytest.mark.parametrize("operation", [_preview, _restore])
async def test_version_operations_preserve_a_dirty_workspace(
    project_id: str, dirty_chain: VersionChain, operation: VersionOperation
) -> None:
    with pytest.raises(versioning.WorkspaceLocked) as excinfo:
        await operation(project_id, dirty_chain.shas[1])

    assert excinfo.value.payload["code"] == "dirty_workspace"
    assert excinfo.value.payload["files"] == ["a.txt", "scratch.txt"]
    assert (dirty_chain.workspace / "a.txt").read_text() == "MANUAL-EDIT"
    assert not dirty_chain.git.is_detached()


@pytest.mark.parametrize("operation", [_preview, _restore])
async def test_version_operations_refuse_an_active_run(
    project_id: str, version_chain: VersionChain, operation: VersionOperation
) -> None:
    claimed_at = await versioning.begin_turn(project_id)
    assert claimed_at is not None
    try:
        with pytest.raises(versioning.WorkspaceLocked) as excinfo:
            await operation(project_id, version_chain.shas[1])
    finally:
        await clear_heartbeat(project_id, only_beat=claimed_at)

    assert excinfo.value.payload["code"] == "run_active"
    assert not version_chain.git.is_detached()


async def test_begin_turn_refuses_a_detached_workspace(project_id: str, version_chain: VersionChain) -> None:
    await version_chain.git.checkout(version_chain.shas[0])

    with pytest.raises(versioning.WorkspaceLocked) as excinfo:
        await versioning.begin_turn(project_id)

    assert excinfo.value.payload["code"] == "previewing"


async def test_reconnect_keeps_a_detached_preview(project_id: str, version_chain: VersionChain) -> None:
    await version_chain.git.checkout(version_chain.shas[0])
    queue = subscribe(project_id)
    try:
        await versioning.broadcast_current_version(project_id)
    finally:
        unsubscribe(project_id, queue)

    current = queue.get_nowait()
    assert current["type"] == "version_preview_active"
    assert current["is_latest"] is False
    assert version_chain.git.is_detached()
    assert (version_chain.workspace / "a.txt").read_text() == "zero"


async def test_workspace_reports_busy_while_another_pod_holds_the_lock(
    project_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ADVISORY_LOCK_WAIT_TIMEOUT", 1)
    async with database.get_engine().connect() as other_pod:
        await other_pod.execute(select(func.pg_advisory_xact_lock(LockNamespace.workspace, func.hashtext(project_id))))
        with pytest.raises(versioning.WorkspaceLocked) as excinfo:
            await versioning.require_writable(project_id)

    assert excinfo.value.payload["code"] == "busy"


@pytest.mark.parametrize("target_index", [0, 1])
async def test_restore_moves_git_and_trims_event_and_message_history(
    project_id: str, version_chain: VersionChain, target_index: int
) -> None:
    versions = await get_versions(project_id)
    target = versions[target_index]
    assert target.payload["_ts"]
    async with database.async_session() as session:
        session.add(ChatMessage(project_id=project_id, role=ChatRole.user, content="keep", created_at="0001-01-01"))
        session.add(
            ChatMessage(
                project_id=project_id,
                role=ChatRole.assistant,
                content="trim",
                created_at="9999-12-31T23:59:59",
            )
        )
        await session.commit()
    await versioning.restore_version(project_id, version_chain.shas[target_index])

    assert [event.payload["commit_sha"] for event in await get_versions(project_id)] == list(
        version_chain.shas[: target_index + 1]
    )
    assert [message.content for message in await get_messages(project_id)] == ["keep"]
    assert await version_chain.git.head_sha() == version_chain.shas[target_index]
    assert not version_chain.git.is_detached()


async def test_new_history_continues_from_the_restored_version(project_id: str, version_chain: VersionChain) -> None:
    await versioning.restore_version(project_id, version_chain.shas[1])
    (version_chain.workspace / "a.txt").write_text("replacement")

    replacement = await versioning.commit_turn(project_id)

    assert replacement
    assert await version_chain.git._run("rev-parse", f"{replacement}^") == version_chain.shas[1]
    assert [event.payload["commit_sha"] for event in await get_versions(project_id)] == [
        version_chain.shas[0],
        version_chain.shas[1],
        replacement,
    ]


async def test_failed_restore_keeps_history_and_resynchronizes_the_real_head(
    project_id: str, version_chain: VersionChain
) -> None:
    invalid = "0" * 40
    await emit_event(project_id, {"type": "version_committed", "commit_sha": invalid}, notify=False)
    queue = subscribe(project_id)
    try:
        with pytest.raises(GitError):
            await versioning.restore_version(project_id, invalid)
    finally:
        unsubscribe(project_id, queue)

    assert len(await get_versions(project_id)) == 4
    assert await version_chain.git.head_sha() == version_chain.shas[2]
    assert queue.get_nowait() == {
        "type": "version_preview_active",
        "commit_sha": version_chain.shas[2],
        "is_latest": True,
    }


async def test_saved_user_edits_stay_out_of_the_next_ai_version(project_id: str, version_chain: VersionChain) -> None:
    (version_chain.workspace / "user.txt").write_text("mine")
    await versioning.save_version(project_id)
    (version_chain.workspace / "ai.txt").write_text("theirs")

    ai_sha = await versioning.commit_turn(project_id)

    versions = await get_versions(project_id)
    assert [event.payload["author"] for event in versions[-2:]] == ["user", "ai"]
    assert [d["path"] for d in versions[-2].payload["diffs"]] == ["user.txt"]
    assert ai_sha
    assert (await version_chain.git._run("diff", "--name-only", f"{ai_sha}~1", ai_sha)).splitlines() == ["ai.txt"]


async def test_save_version_records_diffs_and_tells_the_agent(project_id: str, version_chain: VersionChain) -> None:
    (version_chain.workspace / "a.txt").write_text("edited by hand\n")
    (version_chain.workspace / "new.txt").write_text("mine\n")

    await versioning.save_version(project_id)

    payload = (await get_versions(project_id))[-1].payload
    assert {d["path"]: d["is_new"] for d in payload["diffs"]} == {"a.txt": False, "new.txt": True}
    assert "+edited by hand" in next(d["diff"] for d in payload["diffs"] if d["path"] == "a.txt")
    notes = await get_messages(project_id)
    assert [(m.role, m.content) for m in notes] == [(ChatRole.user, "[I edited these files myself: a.txt, new.txt]")]
    assert notes[0].created_at < payload["_ts"]


async def test_save_version_keeps_file_names_of_oversized_diffs(
    project_id: str, version_chain: VersionChain, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(versioning, "_MAX_DIFF_CHARS", 10)
    (version_chain.workspace / "a.txt").write_text("a much longer body than the cap allows\n")

    await versioning.save_version(project_id)

    assert (await get_versions(project_id))[-1].payload["diffs"] == [{"path": "a.txt", "diff": "", "is_new": False}]
    assert [m.content for m in await get_messages(project_id)] == ["[I edited these files myself: a.txt]"]


@pytest.mark.parametrize(("restore_to_user_edit", "surviving_notes"), [(True, 1), (False, 0)])
async def test_restore_keeps_the_edit_note_only_while_the_edits_survive(
    project_id: str, version_chain: VersionChain, restore_to_user_edit: bool, surviving_notes: int
) -> None:
    (version_chain.workspace / "a.txt").write_text("edited by hand\n")
    await versioning.save_version(project_id)
    versions = await get_versions(project_id)
    target = versions[-1] if restore_to_user_edit else versions[-2]

    await versioning.restore_version(project_id, target.payload["commit_sha"])

    assert len(await get_messages(project_id)) == surviving_notes


async def test_discard_removes_tracked_and_untracked_edits_and_broadcasts(
    project_id: str, dirty_chain: VersionChain
) -> None:
    queue = subscribe(project_id)
    try:
        await versioning.discard_edits(project_id)
    finally:
        unsubscribe(project_id, queue)

    assert (dirty_chain.workspace / "a.txt").read_text() == "two"
    assert not (dirty_chain.workspace / "scratch.txt").exists()
    assert not await dirty_chain.git.is_dirty()
    assert queue.get_nowait() == {"type": "workspace_reset"}
    assert queue.get_nowait() == {"type": "workspace_dirty", "files": []}


async def test_connect_broadcast_reports_unsaved_files(project_id: str, dirty_chain: VersionChain) -> None:
    queue = subscribe(project_id)
    try:
        await versioning.broadcast_current_version(project_id)
    finally:
        unsubscribe(project_id, queue)

    assert queue.get_nowait()["type"] == "version_preview_active"
    assert queue.get_nowait() == {"type": "workspace_dirty", "files": ["a.txt", "scratch.txt"]}


async def test_legacy_nested_workspace_gets_its_own_baseline(project_id: str, workspace: Path, tmp_path: Path) -> None:
    outer_head = outer_repo(tmp_path)
    (workspace / "a.txt").write_text("x")

    await versioning.broadcast_current_version(project_id)

    git = Git(project_id)
    versions = await get_versions(project_id)
    assert git.is_repo()
    assert await git.head_sha() != outer_head
    assert [event.payload["commit_sha"] for event in versions] == [await git.head_sha()]


async def _platform_file_at_head(project_id: str, chain: VersionChain) -> Path:
    client = chain.workspace / "src" / "api" / "client.ts"
    client.parent.mkdir(parents=True)
    client.write_text("platform v1\n")
    assert await versioning.commit_turn(project_id)
    return client


def _platform_sync(workspace: Path, tmp_path: Path) -> Callable[[], str]:
    template = tmp_path / "template"
    (template / "src" / "api").mkdir(parents=True)
    (template / "src" / "api" / "client.ts").write_text("platform v2\n")
    return partial(sync_protected_template_files, str(workspace), str(template))


async def test_platform_update_commits_as_a_system_version(
    project_id: str, version_chain: VersionChain, tmp_path: Path
) -> None:
    client = await _platform_file_at_head(project_id, version_chain)

    summary = _platform_sync(version_chain.workspace, tmp_path)()
    await versioning.save_version(project_id, message=versioning.PLATFORM_UPDATE_MESSAGE, author="system")

    payload = (await get_versions(project_id))[-1].payload
    assert summary.startswith("updated 1")
    assert payload["author"] == "system"
    assert [d["path"] for d in payload["diffs"]] == ["src/api/client.ts"]
    assert await version_chain.git._run("log", "-1", "--format=%s") == "Platform update"
    assert client.read_text() == "platform v2\n"
    assert await get_messages(project_id) == []


async def test_template_sync_without_a_repo_writes_files_and_commits_nothing(
    project_id: str, workspace: Path, tmp_path: Path
) -> None:
    summary = _platform_sync(workspace, tmp_path)()

    assert summary.endswith("created [src/api/client.ts]")
    assert (workspace / "src" / "api" / "client.ts").read_text() == "platform v2\n"
    assert not Git(project_id).is_repo()
    assert await get_versions(project_id) == []


async def test_template_sync_skips_a_workspace_that_is_not_on_this_pod(project_id: str, tmp_path: Path) -> None:
    summary = _platform_sync(tmp_path / "gone", tmp_path)()

    assert summary == "workspace not present on this pod, skipped"
    assert not (tmp_path / "gone").exists()
