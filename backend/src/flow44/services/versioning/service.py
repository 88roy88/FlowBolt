from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from flow44.db.chat import trim_messages_after
from flow44.db.events import emit_event, emit_transient, get_versions, trim_events_after
from flow44.db.heartbeat import is_run_active
from flow44.services.versioning.git_service import GitService

if TYPE_CHECKING:
    from fastapi import WebSocket

    from flow44.sandbox.main import PnpmSandbox

logger = logging.getLogger(__name__)

_V0_MESSAGE = "Version 0 — blank scaffold"

_locks: dict[str, asyncio.Lock] = {}


class UnknownVersionError(RuntimeError):
    pass


def _get_lock(project_id: str) -> asyncio.Lock:
    lock = _locks.get(project_id)
    if lock is None:
        lock = _locks[project_id] = asyncio.Lock()
    return lock


@asynccontextmanager
async def _locked_git(sandbox: PnpmSandbox, project_id: str) -> AsyncIterator[GitService]:
    async with _get_lock(project_id):
        yield GitService(sandbox)


async def _emit_committed(project_id: str, sha: str | None, *, notify: bool = True) -> str | None:
    if sha:
        await emit_event(project_id, {"type": "version_committed", "commit_sha": sha}, notify=notify)
    return sha


async def init_scaffold_version(sandbox: PnpmSandbox, project_id: str) -> None:
    try:
        async with _locked_git(sandbox, project_id) as git:
            sha = await git.init(_V0_MESSAGE)
        await _emit_committed(project_id, sha, notify=False)  # no client connected at scaffold time
    except Exception:
        logger.exception("[versioning] scaffold v0 init failed for %s", project_id)


async def commit_turn(sandbox: PnpmSandbox, project_id: str) -> str | None:
    try:
        async with _locked_git(sandbox, project_id) as git:
            message = f"Version {await git.commit_count()}"
            if not await git.is_repo():
                sha = await git.init(message)  # TODO(legacy): drop once every project has a v0 baseline
            elif await git.current_is_detached():
                logger.warning("[versioning] refusing to commit while detached for %s", project_id)
                return None
            else:
                sha = await git.commit_all(message)
        return await _emit_committed(project_id, sha)
    except Exception:
        logger.exception("[versioning] commit_turn failed for %s", project_id)
        return None


async def preview_version(sandbox: PnpmSandbox, project_id: str, commit_sha: str) -> None:
    versions = await get_versions(project_id)
    if not any(v.payload.get("commit_sha") == commit_sha for v in versions):
        raise UnknownVersionError(commit_sha)  # never hand raw client input to git
    is_latest = versions[-1].payload.get("commit_sha") == commit_sha
    async with _locked_git(sandbox, project_id) as git:
        await (git.checkout_latest() if is_latest else git.checkout(commit_sha))
    await emit_transient(
        project_id, {"type": "version_preview_active", "commit_sha": commit_sha, "is_latest": is_latest}
    )


async def exit_preview(sandbox: PnpmSandbox, project_id: str) -> None:
    async with _locked_git(sandbox, project_id) as git:
        await git.checkout_latest()
    await emit_transient(project_id, {"type": "version_preview_active", "commit_sha": "", "is_latest": True})


async def ensure_at_latest(sandbox: PnpmSandbox, project_id: str) -> None:
    try:
        async with _locked_git(sandbox, project_id) as git:
            if await git.is_repo() and await git.current_is_detached():
                await git.checkout_latest()
    except Exception:
        logger.exception("[versioning] ensure_at_latest failed for %s", project_id)


async def is_previewing(sandbox: PnpmSandbox, project_id: str) -> bool:
    async with _locked_git(sandbox, project_id) as git:
        return await git.is_repo() and await git.current_is_detached()


async def restore_version(sandbox: PnpmSandbox, project_id: str, commit_sha: str) -> None:
    versions = await get_versions(project_id)
    target = next((v for v in versions if v.payload.get("commit_sha") == commit_sha), None)
    if target is None or target.id is None:
        raise UnknownVersionError(commit_sha)
    async with _locked_git(sandbox, project_id) as git:
        await git.reset_hard(commit_sha)
    await trim_events_after(project_id, target.id)
    if target.created_at:
        await trim_messages_after(project_id, target.created_at.isoformat())
    await emit_transient(project_id, {"type": "version_restored", "commit_sha": commit_sha})


async def reject_edit_while_previewing(websocket: WebSocket, sandbox: PnpmSandbox, project_id: str) -> bool:
    if await is_previewing(sandbox, project_id):
        await websocket.send_json({"type": "error", "message": "Restore this version before editing"})
        return True
    return False


async def handle_version_message(
    websocket: WebSocket, sandbox: PnpmSandbox, project_id: str, msg_type: str, data: dict[str, Any]
) -> None:
    if await is_run_active(project_id):
        await websocket.send_json({"type": "error", "message": "Can't change versions while the AI is working"})
        return
    try:
        if msg_type == "exit_preview":
            await exit_preview(sandbox, project_id)
        elif msg_type == "preview_version":
            await preview_version(sandbox, project_id, data["commit_sha"])
        else:
            await restore_version(sandbox, project_id, data["commit_sha"])
    except Exception:
        logger.exception("[versioning] %s failed for %s", msg_type, project_id)
        await websocket.send_json({"type": "error", "message": "Version operation failed"})
