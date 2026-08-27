from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Literal

from flow44.db.chat import trim_messages_after
from flow44.db.events import emit_event, emit_transient, get_versions, trim_events_after
from flow44.db.heartbeat import is_run_active, try_claim_run
from flow44.services.versioning.git import Git

logger = logging.getLogger(__name__)

OnDirty = Literal["save", "discard"]

_SCAFFOLD_MESSAGE = "Version 0 — blank scaffold"
_TURN_MESSAGE = "Version"
_USER_EDITS_MESSAGE = "Your edits"

_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


class UnknownVersionError(RuntimeError):
    pass


class DirtyWorkspaceError(RuntimeError):
    pass


class RunActiveError(RuntimeError):
    pass


class PreviewActiveError(RuntimeError):
    pass


@asynccontextmanager
async def _exclusive_git(project_id: str) -> AsyncIterator[Git]:
    async with _locks[project_id]:
        yield Git(project_id)


# -- Reading the version list --


async def _newest_version(project_id: str) -> str | None:
    versions = await get_versions(project_id)
    return versions[-1].payload["commit_sha"] if versions else None


async def _version_exists(project_id: str, commit_sha: str) -> bool:
    return any(v.payload["commit_sha"] == commit_sha for v in await get_versions(project_id))


# -- Telling clients --


async def _emit_committed(
    project_id: str, sha: str, *, author: str = "ai", files: list[str] | None = None, notify: bool = True
) -> None:
    payload: dict[str, Any] = {"type": "version_committed", "commit_sha": sha, "author": author}
    if files:
        payload["files"] = files
    await emit_event(project_id, payload, notify=notify)


async def _emit_current_version(project_id: str, git: Git) -> None:
    head = await git.head_sha()
    is_latest = head == await _newest_version(project_id)
    await emit_transient(project_id, {"type": "version_preview_active", "commit_sha": head, "is_latest": is_latest})


# -- Unsaved edits --


async def _commit_unsaved_edits(project_id: str, git: Git, on_dirty: OnDirty | None) -> None:
    if not await git.is_dirty():
        return
    if on_dirty is None:
        raise DirtyWorkspaceError
    if on_dirty == "discard":
        return
    files = await git.changed_files()
    sha = await git.commit_all(_USER_EDITS_MESSAGE)
    if sha:
        await _emit_committed(project_id, sha, author="user", files=files)


# -- The version operations --


async def _preview_version(project_id: str, git: Git, commit_sha: str, on_dirty: OnDirty | None) -> None:
    if not await _version_exists(project_id, commit_sha):
        raise UnknownVersionError(commit_sha)  # never hand raw client input to git
    await _commit_unsaved_edits(project_id, git, on_dirty)
    if commit_sha == await _newest_version(project_id):
        await git.checkout_latest()  # viewing the newest version is the same as not previewing at all
    else:
        await git.checkout(commit_sha)
    await _emit_current_version(project_id, git)


async def _exit_preview(project_id: str, git: Git) -> None:
    await git.checkout_latest()
    await _emit_current_version(project_id, git)


async def _restore_version(project_id: str, git: Git, commit_sha: str, on_dirty: OnDirty | None) -> None:
    target = next((v for v in await get_versions(project_id) if v.payload["commit_sha"] == commit_sha), None)
    if target is None or target.id is None:
        raise UnknownVersionError(commit_sha)
    await _commit_unsaved_edits(project_id, git, on_dirty)
    await git.restore_main(commit_sha)
    await trim_events_after(project_id, target.id)
    if target.created_at:
        await trim_messages_after(project_id, target.created_at.isoformat())
    await emit_transient(project_id, {"type": "version_restored", "commit_sha": commit_sha})


async def _bootstrap_legacy(project_id: str, git: Git) -> str | None:
    sha = await git.init(_SCAFFOLD_MESSAGE)  # TODO(legacy): drop once every project has a v0 baseline
    if sha:
        await _emit_committed(project_id, sha)
    return sha


# -- Public API: the caller handles the errors these raise --


async def handle_version_op(project_id: str, op: str, commit_sha: str, on_dirty: OnDirty | None) -> None:
    async with _exclusive_git(project_id) as git:
        if await is_run_active(project_id):
            raise RunActiveError
        if op == "exit_preview":
            await _exit_preview(project_id, git)
        elif op == "preview_version":
            await _preview_version(project_id, git, commit_sha, on_dirty)
        elif op == "restore_version":
            await _restore_version(project_id, git, commit_sha, on_dirty)
        else:
            raise ValueError(f"unknown version op: {op}")


async def save_edits_as_version(project_id: str) -> None:
    async with _exclusive_git(project_id) as git:
        if await is_run_active(project_id):
            raise RunActiveError
        if not await git.is_repo():
            await _bootstrap_legacy(project_id, git)
            return
        if await git.is_detached():
            raise PreviewActiveError
        await _commit_unsaved_edits(project_id, git, "save")


async def claim_run_unless_previewing(project_id: str) -> datetime | None:
    async with _exclusive_git(project_id) as git:
        if await git.is_detached():
            raise PreviewActiveError
        return await try_claim_run(project_id)


# -- Public API: called from paths that must survive a versioning failure, so these swallow and log --


async def init_scaffold_version(project_id: str) -> None:
    try:
        async with _exclusive_git(project_id) as git:
            sha = await git.init(_SCAFFOLD_MESSAGE)
            if sha:
                await _emit_committed(project_id, sha, notify=False)
    except Exception:
        logger.exception("[versioning] scaffold v0 init failed for %s", project_id)


async def commit_turn(project_id: str) -> str | None:
    try:
        async with _exclusive_git(project_id) as git:
            if not await git.is_repo():
                return await _bootstrap_legacy(project_id, git)
            if await git.is_detached():
                logger.warning("[versioning] refusing to commit while detached for %s", project_id)
                return None
            sha = await git.commit_all(_TURN_MESSAGE)
            if sha:
                await _emit_committed(project_id, sha)
            return sha
    except Exception:
        logger.exception("[versioning] commit_turn failed for %s", project_id)
        return None


async def broadcast_current_version(project_id: str, *, reset_orphaned_preview: bool = False) -> None:
    try:
        async with _exclusive_git(project_id) as git:
            if not await git.is_repo():
                return
            if reset_orphaned_preview and await git.is_detached():
                await git.checkout_latest()
            await _emit_current_version(project_id, git)
    except Exception:
        logger.exception("[versioning] version broadcast failed for %s", project_id)
