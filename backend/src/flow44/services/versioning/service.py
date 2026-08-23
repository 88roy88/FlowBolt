from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from flow44.db.chat import trim_messages_after
from flow44.db.events import emit_event, emit_transient, get_versions, trim_events_after
from flow44.services.versioning.git import Git

logger = logging.getLogger(__name__)

_SCAFFOLD_MESSAGE = "Version 0 — blank scaffold"
_TURN_MESSAGE = "Version"

_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


class UnknownVersionError(RuntimeError):
    pass


@asynccontextmanager
async def _locked_git(project_id: str) -> AsyncIterator[Git]:
    async with _locks[project_id]:
        yield Git(project_id)


async def _emit_committed(project_id: str, sha: str | None, *, notify: bool = True) -> str | None:
    if sha:
        await emit_event(project_id, {"type": "version_committed", "commit_sha": sha}, notify=notify)
    return sha


async def init_scaffold_version(project_id: str) -> None:
    try:
        async with _locked_git(project_id) as git:
            sha = await git.init(_SCAFFOLD_MESSAGE)
        await _emit_committed(project_id, sha, notify=False)  # no client connected at scaffold time
    except Exception:
        logger.exception("[versioning] scaffold v0 init failed for %s", project_id)


async def commit_turn(project_id: str) -> str | None:
    try:
        async with _locked_git(project_id) as git:
            if not await git.is_repo():
                sha = await git.init(_SCAFFOLD_MESSAGE)  # TODO(legacy): drop once every project has a v0 baseline
            elif await git.is_detached():
                logger.warning("[versioning] refusing to commit while detached for %s", project_id)
                return None
            else:
                sha = await git.commit_all(_TURN_MESSAGE)
        return await _emit_committed(project_id, sha)
    except Exception:
        logger.exception("[versioning] commit_turn failed for %s", project_id)
        return None


async def preview_version(project_id: str, commit_sha: str) -> None:
    versions = await get_versions(project_id)
    if not any(v.payload.get("commit_sha") == commit_sha for v in versions):
        raise UnknownVersionError(commit_sha)  # never hand raw client input to git
    is_latest = versions[-1].payload.get("commit_sha") == commit_sha
    async with _locked_git(project_id) as git:
        await (git.checkout_latest() if is_latest else git.checkout(commit_sha))
    await emit_transient(
        project_id, {"type": "version_preview_active", "commit_sha": commit_sha, "is_latest": is_latest}
    )


async def exit_preview(project_id: str) -> None:
    async with _locked_git(project_id) as git:
        await git.checkout_latest()
    await emit_transient(project_id, {"type": "version_preview_active", "commit_sha": "", "is_latest": True})


async def emit_preview_state(project_id: str) -> None:
    try:
        versions = await get_versions(project_id)
        async with _locked_git(project_id) as git:
            head = await git.head_sha()
    except Exception:
        logger.exception("[versioning] preview state read failed for %s", project_id)
        return
    latest = versions[-1].payload.get("commit_sha") if versions else None
    await emit_transient(
        project_id, {"type": "version_preview_active", "commit_sha": head, "is_latest": head == latest}
    )


async def ensure_at_latest(project_id: str) -> None:
    try:
        async with _locked_git(project_id) as git:
            if await git.is_detached():
                await git.checkout_latest()
    except Exception:
        logger.exception("[versioning] ensure_at_latest failed for %s", project_id)


async def is_previewing(project_id: str) -> bool:
    async with _locked_git(project_id) as git:
        return await git.is_detached()


async def restore_version(project_id: str, commit_sha: str) -> None:
    versions = await get_versions(project_id)
    target = next((v for v in versions if v.payload.get("commit_sha") == commit_sha), None)
    if target is None or target.id is None:
        raise UnknownVersionError(commit_sha)
    async with _locked_git(project_id) as git:
        await git.restore_main(commit_sha)
    await trim_events_after(project_id, target.id)
    if target.created_at:
        await trim_messages_after(project_id, target.created_at.isoformat())
    await emit_transient(project_id, {"type": "version_restored", "commit_sha": commit_sha})
