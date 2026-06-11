from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from flow44.ai.agent_runtime import mark_agent_finished, mark_agent_started
from flow44.ai.agents.execute.agent import ExecuteAgent
from flow44.ai.agents.fix_error.agent import FixErrorAgent
from flow44.ai.agents.followup.agent import FollowUpAgent
from flow44.ai.agents.plan.agent import PlanAgent
from flow44.ai.state import BuildState
from flow44.api.deps import Permission, ProjectDep, TokenDep, WsProjectDep, require_ws_permission
from flow44.db.chat import ChatRole, get_messages, save_message
from flow44.db.events import emit_event, get_events, subscribe, unsubscribe
from flow44.db.pending_plan import delete_pending_plan, get_pending_plan
from flow44.logic import data_source as ds_logic
from flow44.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

# HTTP routes — included in main's protected api_router
http_router = APIRouter(prefix="/api/chat", tags=["chat"])

# WebSocket router — auth via Depends() on each endpoint
ws_router = APIRouter()


async def _is_new_project(project_id: str) -> bool:
    """A project is 'new' if no build has completed yet (no action_complete event)."""
    events = await get_events(project_id)
    return not any(e.payload.get("type") == "action_complete" for e in events)


async def _run_agent_safe(project_id: str, coro: Any) -> None:
    mark_agent_started(project_id)
    try:
        await coro
    except Exception:
        logger.exception("[chat] Background agent failed for session %s", project_id)
        await emit_event(project_id, {"type": "phase", "phase": "idle"})
        await emit_event(project_id, {"type": "error", "message": "AI processing failed"})
    finally:
        mark_agent_finished(project_id)


def _start_agent(project_id: str, coro: Any) -> None:
    asyncio.create_task(_run_agent_safe(project_id, coro))


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

    queue = subscribe(project.id)

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

            if msg_type == "message":
                user_content: str = data["content"]
                selected_model: str | None = data.get("model")
                ds_ids: list[int] = data.get("dataSourceIds") or []

                # Save user message (for LLM context in followup agent)
                await save_message(project.id, ChatRole.user, user_content)

                # Emit user_message event (for frontend history reconstruction)
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
                await emit_event(project.id, user_event, notify=False)

                is_new = await _is_new_project(project.id)

                if is_new:
                    # Use PlanAgent for design and planning
                    plan_agent = PlanAgent(
                        project_id=project.id,
                        sandbox=sandbox,
                        model=selected_model,
                        data_source_authorization=data_source_authorization,
                    )
                    _start_agent(
                        project.id,
                        plan_agent.run(
                            user_content,
                            data_source_ids=[str(dsid) for dsid in ds_ids] if ds_ids else None,
                        ),
                    )
                else:
                    followup_agent = FollowUpAgent(
                        project_id=project.id,
                        sandbox=sandbox,
                        model=selected_model,
                        data_source_authorization=data_source_authorization,
                        data_source_ids=[str(dsid) for dsid in ds_ids] if ds_ids else None,
                    )
                    _start_agent(project.id, followup_agent.run(user_content))

            elif msg_type == "plan_response":
                action = data.get("action")
                feedback = data.get("feedback")
                selected_model = data.get("model")

                # Load pending plan from DB
                state_json = await get_pending_plan(project.id)
                if state_json is None:
                    await websocket.send_json({"type": "error", "message": "No pending plan found"})
                    continue

                state = BuildState.model_validate_json(state_json)

                if action == "accept":
                    # Execute the plan with ExecuteAgent
                    await delete_pending_plan(project.id)
                    execute_agent = ExecuteAgent(
                        project_id=project.id,
                        sandbox=sandbox,
                        state=state,
                        model=selected_model or state.model,
                    )
                    _start_agent(project.id, execute_agent.run())

                elif action == "modify" and feedback:
                    # Rebuild plan with feedback using PlanAgent
                    plan_agent = PlanAgent(
                        project_id=project.id,
                        sandbox=sandbox,
                        model=selected_model or state.model,
                    )
                    _start_agent(project.id, plan_agent.rebuild_with_feedback(state, feedback))

            elif msg_type == "fix_error":
                error_message = data.get("error_message", "")
                error_file = data.get("error_file")
                error_line = data.get("error_line")
                error_stack = data.get("error_stack")
                selected_model = data.get("model")

                # Save user message (for LLM context)
                error_desc = f"Fix error: {error_message}"
                if error_file:
                    error_desc += f" in {error_file}"
                await save_message(project.id, ChatRole.user, error_desc)

                # Emit user_message event (for frontend history reconstruction)
                await emit_event(
                    project.id,
                    {
                        "type": "user_message",
                        "content": "",
                        "error_fix_request": {
                            "errorMessage": error_message,
                            "errorFile": error_file,
                            "errorLine": error_line,
                            "errorStack": error_stack,
                        },
                    },
                    notify=False,
                )

                fix_agent = FixErrorAgent(
                    project_id=project.id,
                    sandbox=sandbox,
                    model=selected_model,
                )
                _start_agent(
                    project.id,
                    fix_agent.run(
                        error_message=error_message,
                        error_file=error_file,
                        error_line=error_line,
                        error_stack=error_stack,
                    ),
                )

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
        forward_task.cancel()
        try:
            await forward_task
        except asyncio.CancelledError:
            pass
        unsubscribe(project.id, queue)
