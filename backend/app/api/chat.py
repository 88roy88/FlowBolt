from __future__ import annotations

import json
import logging

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.ai.agents import BuildAgent, FollowUpAgent, FixErrorAgent
from app.ai.helpers import CARD_PREFIX
from app.models.chat import get_messages, save_message
from app.models.project import get_project_by_session

logger = logging.getLogger(__name__)

router = APIRouter()


async def _is_new_project(project_id: str) -> bool:
    history = await get_messages(project_id)
    return not any(m.role == "assistant" for m in history)


@router.get("/api/chat/{session_id}/history")
async def chat_history(session_id: str):
    project = await get_project_by_session(session_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    messages = await get_messages(project.id)
    return [asdict(m) for m in messages]


@router.websocket("/ws/chat/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    logger.info("[chat] WebSocket accepted for session %s", session_id)

    project = await get_project_by_session(session_id)
    if project is None:
        await websocket.send_json({"type": "error", "message": "Unknown session"})
        await websocket.close()
        return

    async def ws_send(msg: dict) -> None:
        await websocket.send_json(msg)

    # BuildAgent persists across messages (holds plan state for approval flow)
    build_agent: BuildAgent | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "message":
                user_content: str = data["content"]
                selected_model: str | None = data.get("model")
                case_ids: list[int] = data.get("caseIds") or []

                # Save user message
                if case_ids:
                    from app.api.package_api import _package_search
                    case_names: list[str] = []
                    for cid in case_ids:
                        try:
                            results = await _package_search(str(cid))
                            name = results[0].get("Name", f"Case #{cid}") if results else f"Case #{cid}"
                        except Exception:
                            name = f"Case #{cid}"
                        case_names.append(name)

                    cases_meta = json.dumps({"type": "cases_context", "caseIds": case_ids, "caseNames": case_names})
                    await save_message(project.id, "user", f"<!--cases-meta:{cases_meta}-->\n{user_content}")
                else:
                    await save_message(project.id, "user", user_content)

                try:
                    is_new = await _is_new_project(project.id)

                    if is_new:
                        build_agent = BuildAgent(
                            session_id=session_id, project_id=project.id,
                            ws_send=ws_send, model=selected_model,
                        )
                        await build_agent.run(
                            user_content,
                            case_ids=[str(cid) for cid in case_ids] if case_ids else None,
                        )
                    else:
                        agent = FollowUpAgent(
                            session_id=session_id, project_id=project.id,
                            ws_send=ws_send, model=selected_model,
                        )
                        await agent.run(user_content)
                except Exception:
                    logger.exception("[chat] Agent error for session %s", session_id)
                    await websocket.send_json({"type": "error", "message": "AI processing failed"})

            elif msg_type == "plan_response":
                action = data.get("action", "reject")
                feedback = data.get("feedback")

                if build_agent is None:
                    await websocket.send_json({"type": "error", "message": "No active build session"})
                    continue

                try:
                    await build_agent.handle_plan_response(action, feedback)
                except Exception:
                    logger.exception("[chat] Plan response error for session %s", session_id)
                    await websocket.send_json({"type": "error", "message": "Plan handling failed"})

            elif msg_type == "fix_error":
                error_message = data.get("error_message", "")
                error_file = data.get("error_file")
                error_line = data.get("error_line")
                error_stack = data.get("error_stack")
                selected_model = data.get("model")

                card_data = {
                    "type": "error_fix_request",
                    "errorMessage": error_message,
                    "errorFile": error_file,
                    "errorLine": error_line,
                    "errorStack": error_stack,
                }
                await save_message(project.id, "user", f"{CARD_PREFIX}{json.dumps(card_data)}-->")

                try:
                    agent = FixErrorAgent(
                        session_id=session_id, project_id=project.id,
                        ws_send=ws_send, model=selected_model,
                    )
                    await agent.run(
                        error_message=error_message,
                        error_file=error_file,
                        error_line=error_line,
                        error_stack=error_stack,
                    )
                except Exception:
                    logger.exception("[chat] Fix error failed for session %s", session_id)
                    await websocket.send_json({"type": "error", "message": "Error fix failed"})

    except WebSocketDisconnect:
        logger.info("[chat] WebSocket disconnected for session %s", session_id)
    except Exception:
        logger.exception("[chat] Unhandled error in chat WebSocket for session %s", session_id)
        try:
            await websocket.send_json({"type": "error", "message": "Internal server error"})
            await websocket.close()
        except Exception:
            pass
