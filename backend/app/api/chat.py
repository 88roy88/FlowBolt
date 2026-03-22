from __future__ import annotations

import asyncio
import json
import logging

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.ai.agents import BuildAgent, FollowUpAgent, FixErrorAgent
from app.ai.agent_registry import register, get as get_agent, remove as remove_agent
from app.models.chat import get_messages, save_message
from app.models.events import subscribe, unsubscribe, get_events, emit_event
from app.models.project import get_project_by_session

logger = logging.getLogger(__name__)

router = APIRouter()


async def _is_new_project(session_id: str) -> bool:
    """A project is 'new' if no build has completed yet (no action_complete event)."""
    events = await get_events(session_id)
    return not any(e.payload.get("type") == "action_complete" for e in events)


async def _run_agent_safe(session_id: str, coro) -> None:
    try:
        await coro
    except Exception:
        logger.exception("[chat] Background agent failed for session %s", session_id)
        await emit_event(session_id, {"type": "error", "message": "AI processing failed"})
    finally:
        remove_agent(session_id)


@router.get("/api/chat/{session_id}/history")
async def chat_history(session_id: str):
    project = await get_project_by_session(session_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    messages = await get_messages(project.id)
    return [asdict(m) for m in messages]


@router.get("/api/chat/{session_id}/events")
async def chat_events(session_id: str):
    events = await get_events(session_id)
    return [{**evt.payload, "_ts": evt.created_at} for evt in events]


@router.websocket("/ws/chat/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    logger.info("[chat] WebSocket accepted for session %s", session_id)

    project = await get_project_by_session(session_id)
    if project is None:
        await websocket.send_json({"type": "error", "message": "Unknown session"})
        await websocket.close()
        return

    # Subscribe to live events (replay is handled by GET /api/chat/{session_id}/events)
    queue = subscribe(session_id)

    async def _forward_events() -> None:
        try:
            while True:
                event = await queue.get()
                await websocket.send_json(event)
        except Exception:
            pass

    async def _receive_actions() -> None:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "message":
                user_content: str = data["content"]
                selected_model: str | None = data.get("model")
                case_ids: list[int] = data.get("caseIds") or []

                raw_pkg_auth = data.get("packageApiAuthorization")
                if isinstance(raw_pkg_auth, str):
                    package_api_authorization: str | None = raw_pkg_auth.strip() or None
                else:
                    package_api_authorization = None

                # Save user message (for LLM context in followup agent)
                await save_message(project.id, "user", user_content)

                # Emit user_message event (for frontend history reconstruction)
                user_event: dict = {"type": "user_message", "content": user_content}
                if case_ids:
                    from app.api.package_api import _package_search

                    case_names: list[str] = []
                    for cid in case_ids:
                        try:
                            results = await _package_search(str(cid), authorization=package_api_authorization)
                            name = results[0].get("Name", f"Case #{cid}") if results else f"Case #{cid}"
                        except Exception:
                            name = f"Case #{cid}"
                        case_names.append(name)
                    user_event["cases"] = [
                        {"id": cid, "name": cname}
                        for cid, cname in zip(case_ids, case_names)
                    ]
                await emit_event(session_id, user_event, notify=False)

                is_new = await _is_new_project(session_id)

                if is_new:
                    agent = BuildAgent(
                        session_id=session_id, project_id=project.id,
                        model=selected_model,
                    )
                    register(session_id, agent)
                    asyncio.create_task(_run_agent_safe(
                        session_id,
                        agent.run(
                            user_content,
                            case_ids=[str(cid) for cid in case_ids] if case_ids else None,
                            package_api_authorization=package_api_authorization,
                        ),
                    ))
                else:
                    agent = FollowUpAgent(
                        session_id=session_id, project_id=project.id,
                        model=selected_model,
                    )
                    register(session_id, agent)
                    asyncio.create_task(_run_agent_safe(session_id, agent.run(user_content)))

            elif msg_type == "plan_response":
                action = data.get("action", "reject")
                feedback = data.get("feedback")

                agent = get_agent(session_id)
                if isinstance(agent, BuildAgent):
                    agent.signal_plan_response(action, feedback)
                else:
                    await websocket.send_json({"type": "error", "message": "No active build session"})

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
                await save_message(project.id, "user", error_desc)

                # Emit user_message event (for frontend history reconstruction)
                await emit_event(session_id, {
                    "type": "user_message",
                    "content": "",
                    "error_fix_request": {
                        "errorMessage": error_message,
                        "errorFile": error_file,
                        "errorLine": error_line,
                        "errorStack": error_stack,
                    },
                }, notify=False)

                agent = FixErrorAgent(
                    session_id=session_id, project_id=project.id,
                    model=selected_model,
                )
                register(session_id, agent)
                asyncio.create_task(_run_agent_safe(
                    session_id,
                    agent.run(error_message=error_message, error_file=error_file, error_line=error_line, error_stack=error_stack),
                ))

    forward_task = asyncio.create_task(_forward_events())

    try:
        await _receive_actions()
    except WebSocketDisconnect:
        logger.info("[chat] WebSocket disconnected for session %s", session_id)
    except Exception:
        logger.exception("[chat] Unhandled error in chat WebSocket for session %s", session_id)
    finally:
        forward_task.cancel()
        try:
            await forward_task
        except asyncio.CancelledError:
            pass
        unsubscribe(session_id, queue)
