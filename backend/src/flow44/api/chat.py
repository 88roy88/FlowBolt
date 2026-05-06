from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from flow44.ai.agents.execute.agent import ExecuteAgent
from flow44.ai.agents.fix_error.agent import FixErrorAgent
from flow44.ai.agents.followup.agent import FollowUpAgent
from flow44.ai.agents.plan.agent import PlanAgent
from flow44.ai.state import BuildState
from flow44.api.auth import ProjectDep, extract_user_id
from flow44.db.chat import ChatRole, get_messages, save_message
from flow44.db.events import emit_event, get_events, subscribe, unsubscribe
from flow44.db.pending_plan import delete_pending_plan, get_pending_plan
from flow44.db.project import get_project as db_get_project
from flow44.integrations.flapi_api import data_source_client
from flow44.sandbox.manager import SandboxNotFoundError, sandbox_manager

logger = logging.getLogger(__name__)

# HTTP routes — included in main's protected api_router
http_router = APIRouter(prefix="/api/chat", tags=["chat"])

# WebSocket route — registered directly on app (browser WS can't send headers)
router = APIRouter()


async def _is_new_project(project_id: str) -> bool:
    """A project is 'new' if no build has completed yet (no action_complete event)."""
    events = await get_events(project_id)
    return not any(e.payload.get("type") == "action_complete" for e in events)


async def _run_agent_safe(project_id: str, coro: Any) -> None:
    try:
        await coro
    except Exception:
        logger.exception("[chat] Background agent failed for session %s", project_id)
        await emit_event(project_id, {"type": "error", "message": "AI processing failed"})


@http_router.get("/{project_id}/history")
async def chat_history(project: ProjectDep) -> list[dict[str, Any]]:
    messages = await get_messages(project.id)
    return [m.model_dump() for m in messages]


@http_router.get("/{project_id}/events")
async def chat_events(project: ProjectDep) -> list[dict[str, Any]]:
    events = await get_events(project.id)
    return [{**evt.payload, "_ts": evt.created_at} for evt in events]


@router.websocket("/ws/chat/{project_id}")
async def chat_ws(websocket: WebSocket, project_id: str) -> None:  # noqa: C901, PLR0915
    await websocket.accept()
    logger.info("[chat] WebSocket accepted for session %s", project_id)

    # --- Step 1: authenticate before any project or sandbox access ---
    try:
        raw_first = await websocket.receive_text()
        first = json.loads(raw_first)
    except Exception:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    if first.get("type") != "auth":
        await websocket.send_json({"type": "error", "message": "Unauthorized"})
        await websocket.close()
        return

    raw_ds_auth = first.get("dataSourceAuthorization")
    data_source_authorization: str | None = raw_ds_auth.strip() or None if isinstance(raw_ds_auth, str) else None
    user_token = first.get("userAuthorization")

    try:
        caller_id = extract_user_id(user_token if isinstance(user_token, str) else None)
    except HTTPException as exc:
        await websocket.send_json({"type": "error", "message": exc.detail})
        await websocket.close()
        return

    # --- Step 2: load and authorize project (unified 404 prevents project enumeration) ---
    project = await db_get_project(project_id)
    if project is None or project.user_id != caller_id:
        await websocket.send_json({"type": "error", "message": "Project not found"})
        await websocket.close()
        return

    # --- Step 3: prepare sandbox (only reached after successful auth) ---
    try:
        sandbox = sandbox_manager.get_sandbox(project_id)
        await sandbox_manager.ensure_ready(sandbox)
    except SandboxNotFoundError:
        logger.error("[chat] Sandbox not found for session %s", project_id)
        await websocket.send_json({"type": "error", "message": "Project sandbox not found"})
        await websocket.close()
        return
    except Exception:
        logger.exception("[chat] Failed to prepare sandbox for session %s", project_id)
        await websocket.send_json({"type": "error", "message": "Failed to prepare project sandbox"})
        await websocket.close()
        return

    # --- Step 4: subscribe to live events and start processing ---
    # (replay is handled by GET /api/chat/{project_id}/events)
    queue = subscribe(project_id)

    async def _forward_events() -> None:
        try:
            while True:
                event = await queue.get()
                await websocket.send_json(event)
        except Exception:
            logger.debug("Event forwarding stopped for session %s", project_id)

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
                        name = await data_source_client.get_display_name(
                            ds_id,
                            authorization=data_source_authorization,
                        )
                        ds_names.append(name)
                    user_event["data_sources"] = [
                        {"id": dsid, "name": dsname} for dsid, dsname in zip(ds_ids, ds_names, strict=True)
                    ]
                await emit_event(project_id, user_event, notify=False)

                is_new = await _is_new_project(project_id)

                if is_new:
                    # Use PlanAgent for design and planning
                    plan_agent = PlanAgent(
                        project_id=project_id,
                        sandbox=sandbox,
                        model=selected_model,
                        data_source_authorization=data_source_authorization,
                    )
                    asyncio.create_task(
                        _run_agent_safe(
                            project_id,
                            plan_agent.run(
                                user_content,
                                data_source_ids=[str(dsid) for dsid in ds_ids] if ds_ids else None,
                            ),
                        )
                    )
                else:
                    followup_agent = FollowUpAgent(
                        project_id=project_id,
                        sandbox=sandbox,
                        model=selected_model,
                    )
                    asyncio.create_task(_run_agent_safe(project_id, followup_agent.run(user_content)))

            elif msg_type == "plan_response":
                action = data.get("action", "reject")
                feedback = data.get("feedback")
                selected_model = data.get("model")

                # Load pending plan from DB
                state_json = await get_pending_plan(project_id)
                if state_json is None:
                    await websocket.send_json({"type": "error", "message": "No pending plan found"})
                    continue

                state = BuildState.model_validate_json(state_json)

                if action == "accept":
                    # Execute the plan with ExecuteAgent
                    await delete_pending_plan(project_id)
                    execute_agent = ExecuteAgent(
                        project_id=project_id,
                        sandbox=sandbox,
                        state=state,
                        model=selected_model or state.model,
                    )
                    asyncio.create_task(_run_agent_safe(project_id, execute_agent.run()))

                elif action == "modify" and feedback:
                    # Rebuild plan with feedback using PlanAgent
                    plan_agent = PlanAgent(
                        project_id=project_id,
                        sandbox=sandbox,
                        model=selected_model or state.model,
                    )
                    asyncio.create_task(_run_agent_safe(project_id, plan_agent.rebuild_with_feedback(state, feedback)))

                elif action == "reject":
                    await delete_pending_plan(project_id)
                    await emit_event(project_id, {"type": "plan_rejected"})
                    await emit_event(project_id, {"type": "phase", "phase": "idle"})

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
                    project_id,
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
                    project_id=project_id,
                    sandbox=sandbox,
                    model=selected_model,
                )
                asyncio.create_task(
                    _run_agent_safe(
                        project_id,
                        fix_agent.run(
                            error_message=error_message,
                            error_file=error_file,
                            error_line=error_line,
                            error_stack=error_stack,
                        ),
                    )
                )

    forward_task = asyncio.create_task(_forward_events())

    try:
        await _receive_actions()
    except WebSocketDisconnect:
        logger.info("[chat] WebSocket disconnected for session %s", project_id)
    except Exception:
        logger.exception("[chat] Unhandled error in chat WebSocket for session %s", project_id)
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
        unsubscribe(project_id, queue)
