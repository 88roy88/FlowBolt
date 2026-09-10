from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from flow44.ai.agents.execute.agent import ExecuteAgent
from flow44.ai.agents.fix_error.agent import FixErrorAgent
from flow44.ai.agents.followup.agent import FollowUpAgent
from flow44.ai.agents.plan.agent import PlanAgent
from flow44.ai.state import BuildState
from flow44.api.deps import Permission, ProjectDep, TokenDep, WsProjectDep, WsUserDep, require_ws_permission
from flow44.config import settings
from flow44.db.chat import ChatRole, get_messages, save_message
from flow44.db.events import emit_event, get_events, has_subscribers, subscribe, unsubscribe
from flow44.db.heartbeat import clear_heartbeat, touch_heartbeat
from flow44.db.pending_plan import delete_pending_plan, get_pending_plan
from flow44.logic import data_source as ds_logic
from flow44.sandbox.manager import sandbox_manager
from flow44.services.versioning import service as versioning
from flow44.services.versioning.git import GitError

logger = logging.getLogger(__name__)

http_router = APIRouter(prefix="/api/chat", tags=["chat"])
ws_router = APIRouter()


async def _is_new_project(project_id: str) -> bool:
    """A project is 'new' if no build has completed yet (no action_complete event)."""
    events = await get_events(project_id)
    return not any(e.payload.get("type") == "action_complete" for e in events)


# Strong refs: asyncio holds tasks weakly, so a run could be GC'd mid-flight.
_RUNNING: set[asyncio.Task[None]] = set()

_AGENT_BUSY = {"type": "error", "message": "An agent is already running for this project"}
_VERSION_FAILED = {"type": "version_error", "message": "Version operation failed", "code": "failed"}


class AgentAlreadyRunning(Exception):
    pass


class _RunBudgetExceeded(Exception):
    """The run outlived AGENT_RUN_TIMEOUT (distinct from a TimeoutError the agent raises)."""


@dataclass
class _Beat:
    """The heartbeat timestamp this run currently owns — its lock token."""

    at: datetime


async def _heartbeat_until_done(project_id: str, run_task: asyncio.Task[Any], beat: _Beat) -> None:
    deadline = time.monotonic() + settings.AGENT_RUN_TIMEOUT
    beat_interval = settings.AGENT_RUN_STALE_TIMEOUT / 4
    while time.monotonic() < deadline:
        timeout = min(beat_interval, deadline - time.monotonic())
        done, _ = await asyncio.wait({run_task}, timeout=timeout)
        if run_task in done:
            return
        try:
            beat.at = await touch_heartbeat(project_id)
        except Exception:
            # A transient DB blip must not tear down a healthy run; the reaper covers a
            # genuinely dead one if writes keep failing past the stale window.
            logger.warning("[chat] Heartbeat write failed for session %s; continuing", project_id, exc_info=True)
    raise _RunBudgetExceeded


async def _cancel_task(task: asyncio.Task[Any]) -> None:
    if task.done():
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def _report_run_failure(project_id: str, message: str) -> None:
    await emit_event(project_id, {"type": "phase", "phase": "idle"})
    await emit_event(project_id, {"type": "error", "message": message})


async def _run_agent_safe(project_id: str, coro: Any, claimed_at: datetime) -> None:
    """Run the agent under a heartbeat + timeout, surfacing failures to the client."""
    run_task = asyncio.create_task(coro)
    beat = _Beat(at=claimed_at)
    try:
        await _heartbeat_until_done(project_id, run_task, beat)
        await run_task
        await versioning.commit_turn(project_id)
    except _RunBudgetExceeded:
        logger.error(
            "[chat] Background agent timed out after %ss for session %s", settings.AGENT_RUN_TIMEOUT, project_id
        )
        # Stop the agent before reporting idle, so a late event can't re-stick the UI.
        await _cancel_task(run_task)
        await _report_run_failure(project_id, "AI processing timed out")
    except Exception:
        logger.exception("[chat] Background agent failed for session %s", project_id)
        await _report_run_failure(project_id, "AI processing failed")
    finally:
        await _cancel_task(run_task)
        await clear_heartbeat(project_id, only_beat=beat.at)


async def _claim_run(project_id: str) -> datetime:
    claimed_at = await versioning.begin_turn(project_id)
    if claimed_at is None:
        raise AgentAlreadyRunning
    return claimed_at


def _start_agent(project_id: str, coro: Any, claimed_at: datetime) -> None:
    task = asyncio.create_task(_run_agent_safe(project_id, coro, claimed_at))
    _RUNNING.add(task)
    task.add_done_callback(_RUNNING.discard)


async def _start_turn(
    project_id: str,
    make_coro: Callable[[], Any],
    prepare: Callable[[], Awaitable[Any]] | None = None,
) -> None:
    claimed_at = await _claim_run(project_id)
    try:
        if prepare is not None:
            await prepare()
        _start_agent(project_id, make_coro(), claimed_at)
    except Exception:
        await clear_heartbeat(project_id, only_beat=claimed_at)
        raise


async def _save_user_turn(project_id: str, content: str, event: dict[str, Any]) -> None:
    await save_message(project_id, ChatRole.user, content)
    await emit_event(project_id, event, notify=False)


@http_router.get("/{project_id}/history")
async def chat_history(project: ProjectDep) -> list[dict[str, Any]]:
    messages = await get_messages(project.id)
    return [m.model_dump() for m in messages]


@http_router.get("/{project_id}/events")
async def chat_events(project: ProjectDep) -> list[dict[str, Any]]:
    events = await get_events(project.id)
    return [{**evt.payload, "_ts": evt.created_at} for evt in events]


@ws_router.websocket("/ws/chat/{project_id}")
async def chat_ws(  # noqa: C901, PLR0915
    websocket: WebSocket,
    project: WsProjectDep,
    user_id: WsUserDep,
    data_source_authorization: TokenDep = None,
    _perms: set[Permission] = require_ws_permission(Permission.write),
) -> None:
    await websocket.accept()
    logger.info("[chat] WebSocket accepted for session %s", project.id)

    try:
        sandbox = await sandbox_manager.wake_sandbox(project.id)
    except Exception:
        logger.exception("[chat] Failed to prepare sandbox for session %s", project.id)
        await websocket.send_json({"type": "error", "message": "Failed to prepare project sandbox"})
        await websocket.close()
        return

    had_subscribers = has_subscribers(project.id)
    queue = subscribe(project.id)
    await versioning.broadcast_current_version(project.id, reset_orphaned_preview=not had_subscribers)

    async def _forward_events() -> None:
        try:
            while True:
                event = await queue.get()
                await websocket.send_json(event)
        except Exception:
            logger.debug("Event forwarding stopped for session %s", project.id)

    async def _receive_actions() -> None:  # noqa: C901, PLR0912, PLR0915
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            try:
                if msg_type == "message":
                    user_content: str = data["content"]
                    selected_model: str | None = data.get("model")
                    ds_ids: list[int] = data.get("dataSourceIds") or []

                    user_event: dict[str, Any] = {"type": "user_message", "content": user_content}
                    if ds_ids:
                        ds_names: list[str] = []
                        for ds_id in ds_ids:
                            name = await ds_logic.get_display_name(
                                ds_id,
                                authorization=data_source_authorization,
                            )
                            ds_names.append(name)
                        user_event["data_sources"] = [
                            {"id": dsid, "name": dsname} for dsid, dsname in zip(ds_ids, ds_names, strict=True)
                        ]

                    agent_cls = PlanAgent if await _is_new_project(project.id) else FollowUpAgent
                    agent = agent_cls(
                        project_id=project.id,
                        sandbox=sandbox,
                        model=selected_model,
                        user_id=user_id,
                        data_source_authorization=data_source_authorization,
                    )
                    source_ids = [str(dsid) for dsid in ds_ids] if ds_ids else None
                    # Claim first: a refused turn must not leave the message behind.
                    await _start_turn(
                        project.id,
                        partial(agent.run, user_content, data_source_ids=source_ids),
                        prepare=partial(_save_user_turn, project.id, user_content, user_event),
                    )

                elif msg_type == "plan_response":
                    action = data.get("action")
                    feedback = data.get("feedback")
                    selected_model = data.get("model")

                    state_json = await get_pending_plan(project.id)
                    if state_json is None:
                        await websocket.send_json({"type": "error", "message": "No pending plan found"})
                        continue

                    state = BuildState.model_validate_json(state_json)

                    if action == "accept":
                        execute_agent = ExecuteAgent(
                            project_id=project.id,
                            sandbox=sandbox,
                            state=state,
                            model=selected_model or state.model,
                            user_id=user_id,
                        )
                        # before the delete: a refusal must not lose the plan
                        await _start_turn(
                            project.id,
                            execute_agent.run,
                            prepare=partial(delete_pending_plan, project.id),
                        )

                    elif action == "modify" and feedback:
                        plan_agent = PlanAgent(
                            project_id=project.id,
                            sandbox=sandbox,
                            model=selected_model or state.model,
                            user_id=user_id,
                        )
                        await _start_turn(project.id, partial(plan_agent.rebuild_with_feedback, state, feedback))

                elif msg_type == "fix_error":
                    error_message = data.get("error_message", "")
                    error_file = data.get("error_file")
                    error_line = data.get("error_line")
                    error_stack = data.get("error_stack")
                    selected_model = data.get("model")

                    error_desc = f"Fix error: {error_message}"
                    if error_file:
                        error_desc += f" in {error_file}"
                    fix_event: dict[str, Any] = {
                        "type": "user_message",
                        "content": "",
                        "error_fix_request": {
                            "errorMessage": error_message,
                            "errorFile": error_file,
                            "errorLine": error_line,
                            "errorStack": error_stack,
                        },
                    }
                    fix_agent = FixErrorAgent(
                        project_id=project.id,
                        sandbox=sandbox,
                        model=selected_model,
                        user_id=user_id,
                    )
                    await _start_turn(
                        project.id,
                        partial(
                            fix_agent.run,
                            error_message=error_message,
                            error_file=error_file,
                            error_line=error_line,
                            error_stack=error_stack,
                        ),
                        prepare=partial(_save_user_turn, project.id, error_desc, fix_event),
                    )

                else:
                    await versioning.handle_action(project.id, msg_type, data)
            except AgentAlreadyRunning:
                await websocket.send_json(_AGENT_BUSY)
            except versioning.WorkspaceLocked as exc:
                await websocket.send_json(exc.payload)
            except (GitError, versioning.UnknownVersionError):
                logger.exception("[versioning] %s failed for %s", msg_type, project.id)
                await websocket.send_json(_VERSION_FAILED)

    forward_task = asyncio.create_task(_forward_events())

    try:
        await _receive_actions()
    except WebSocketDisconnect:
        logger.info("[chat] WebSocket disconnected for session %s", project.id)
    except Exception:
        logger.exception("[chat] Unhandled error in chat WebSocket for session %s", project.id)
        try:
            await websocket.send_json({"type": "error", "message": "Internal server error"})
        except Exception:  # noqa: S110 — WS may already be closed
            pass
    finally:
        await _cancel_task(forward_task)
        unsubscribe(project.id, queue)
