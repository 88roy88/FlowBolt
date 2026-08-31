from __future__ import annotations

import asyncio
import logging
import shutil
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path
from typing import Any

from flow44.config import settings
from flow44.db.chat import trim_messages_after
from flow44.db.events import AgentEvent, emit_event, emit_transient, get_versions, trim_events_after
from flow44.db.heartbeat import is_run_active, try_claim_run
from flow44.services.versioning.git import Git

logger = logging.getLogger(__name__)

_SCAFFOLD_MESSAGE = "Version 0 — blank scaffold"
_TURN_MESSAGE = "Version"
_USER_EDITS_MESSAGE = "Your edits"

_MESSAGES = {
    "run_active": "Can't edit while the AI is working",
    "previewing": "Restore this version before editing",
    "dirty_workspace": "You have unsaved edits",
}

_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


class UnknownVersionError(RuntimeError):
    pass


class WorkspaceLocked(RuntimeError):
    def __init__(self, code: str, files: list[str] | None = None) -> None:
        super().__init__(code)
        self.payload = {
            "type": "version_error",
            "code": code,
            "message": _MESSAGES[code],
            "files": files or [],
        }


# -- The lock --


async def _refuse_if_busy(project_id: str) -> None:
    if await is_run_active(project_id):
        raise WorkspaceLocked("run_active")


async def _refuse_if_dirty(git: Git) -> None:
    if await git.is_dirty():
        raise WorkspaceLocked("dirty_workspace", await git.changed_files())


async def _needs_writable(project_id: str, git: Git) -> None:
    await _refuse_if_busy(project_id)
    if git.is_detached():
        raise WorkspaceLocked("previewing")


async def _needs_settled(project_id: str, git: Git) -> None:
    await _refuse_if_busy(project_id)
    await _refuse_if_dirty(git)


async def _needs_turn(project_id: str, git: Git) -> None:
    await _needs_writable(project_id, git)
    await _refuse_if_dirty(git)


Precondition = Callable[[str, Git], Awaitable[None]]


def _seed_gitignore(workspace_dir: str) -> None:
    target = Path(workspace_dir, ".gitignore")
    if not target.exists():
        shutil.copy(Path(settings.TEMPLATE_DIR, ".gitignore"), target)


async def _ensure_repo(project_id: str, git: Git) -> None:
    if git.is_repo():
        return
    _seed_gitignore(git.workspace_dir)
    sha = await git.init(_SCAFFOLD_MESSAGE)
    if sha:
        await _emit_committed(project_id, sha)


@asynccontextmanager
async def _workspace(project_id: str, needs: Precondition | None = None) -> AsyncIterator[Git]:
    async with _locks[project_id]:
        git = Git(project_id)
        await _ensure_repo(project_id, git)
        if needs:
            await needs(project_id, git)
        try:
            yield git
        except Exception:
            with suppress(Exception):
                await _emit_current_version(project_id, git)
            raise


# -- Reading the version list --


def _find(versions: list[AgentEvent], commit_sha: str) -> AgentEvent | None:
    return next((v for v in versions if v.payload["commit_sha"] == commit_sha), None)


def _newest_sha(versions: list[AgentEvent]) -> str | None:
    return versions[-1].payload["commit_sha"] if versions else None


# -- Telling clients --


async def _emit_committed(project_id: str, sha: str, *, author: str = "ai", files: list[str] | None = None) -> None:
    payload: dict[str, Any] = {"type": "version_committed", "commit_sha": sha, "author": author}
    if files:
        payload["files"] = files
    await emit_event(project_id, payload)


async def _emit_current_version(project_id: str, git: Git) -> None:
    head = await git.head_sha()
    is_latest = head == _newest_sha(await get_versions(project_id))
    await emit_transient(project_id, {"type": "version_preview_active", "commit_sha": head, "is_latest": is_latest})


# -- Public API: the caller handles the errors these raise --


async def ensure_repo(project_id: str) -> None:
    async with _workspace(project_id):
        pass


async def require_writable(project_id: str) -> None:
    async with _workspace(project_id, _needs_writable):
        pass


async def begin_turn(project_id: str) -> datetime | None:
    async with _workspace(project_id, _needs_turn):
        return await try_claim_run(project_id)


async def save_version(project_id: str) -> None:
    async with _workspace(project_id, _needs_writable) as git:
        if not await git.is_dirty():
            return
        files = await git.changed_files()
        sha = await git.commit_all(_USER_EDITS_MESSAGE)
        if sha:
            await _emit_committed(project_id, sha, author="user", files=files)


async def discard_edits(project_id: str) -> None:
    async with _workspace(project_id, _needs_writable) as git:
        await git.discard_all()


async def preview_version(project_id: str, commit_sha: str) -> None:
    async with _workspace(project_id, _needs_settled) as git:
        versions = await get_versions(project_id)
        if _find(versions, commit_sha) is None:
            raise UnknownVersionError(commit_sha)  # never hand raw client input to git
        if commit_sha == _newest_sha(versions):
            await git.checkout_latest()  # viewing the newest version is the same as not previewing at all
        else:
            await git.checkout(commit_sha)
        await _emit_current_version(project_id, git)


async def exit_preview(project_id: str) -> None:
    async with _workspace(project_id) as git:
        await git.checkout_latest()
        await _emit_current_version(project_id, git)


async def restore_version(project_id: str, commit_sha: str) -> None:
    async with _workspace(project_id, _needs_settled) as git:
        target = _find(await get_versions(project_id), commit_sha)
        if target is None or target.id is None:
            raise UnknownVersionError(commit_sha)
        await git.restore_main(commit_sha)
        await trim_events_after(project_id, target.id)
        if target.created_at:
            await trim_messages_after(project_id, target.created_at.isoformat())
        await emit_transient(project_id, {"type": "version_restored", "commit_sha": commit_sha})


# -- Public API: called from paths that must survive a versioning failure, so these swallow and log --


async def commit_turn(project_id: str) -> str | None:
    try:
        async with _workspace(project_id) as git:
            if git.is_detached():
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
        async with _workspace(project_id) as git:
            if reset_orphaned_preview and git.is_detached():
                await git.checkout_latest()
            await _emit_current_version(project_id, git)
    except Exception:
        logger.exception("[versioning] version broadcast failed for %s", project_id)
