"""WebSocket endpoint for AI chat interactions."""

from __future__ import annotations

import json
import logging

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.ai.agent import AgentOrchestrator
from app.models.chat import get_messages, save_message
from app.models.project import get_project_by_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/chat/{session_id}/history")
async def chat_history(session_id: str):
    """Return saved chat messages for a session."""
    project = await get_project_by_session(session_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    messages = await get_messages(project.id)
    return [asdict(m) for m in messages]


@router.websocket("/ws/chat/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: str) -> None:
    """Bidirectional WebSocket for chat.

    Client sends::

        {"type": "message", "content": "user prompt text"}
        {"type": "plan_response", "action": "accept" | "reject" | "modify", "feedback": "..."}
        {"type": "fix_error", "error_message": "...", "error_file": "...", "error_line": 123, "error_stack": "..."}

    Server sends a stream of::

        {"type": "phase", "phase": "classifying" | "designing" | "planning" | "awaiting_approval" | "executing" | "complete"}
        {"type": "design_progress", "stream": "architecture" | "ux", "content": "..."}
        {"type": "work_plan", "plan": {...}}
        {"type": "task_update", "taskId": "...", "status": "running" | "completed" | "failed", "file": "..."}
        {"type": "text", "content": "..."}
        {"type": "file", "path": "...", "content": "..."}
        {"type": "shell_output", "command": "...", "output": "..."}
        {"type": "action_complete"}
    """
    await websocket.accept()
    logger.info("[chat] WebSocket accepted for session %s", session_id)

    project = await get_project_by_session(session_id)
    if project is None:
        logger.warning("[chat] No project found for session %s", session_id)
        await websocket.send_json({"type": "error", "message": "Unknown session"})
        await websocket.close()
        return

    logger.info("[chat] Project %s found for session %s", project.id, session_id)

    async def ws_send(msg: dict) -> None:
        await websocket.send_json(msg)

    orchestrator = AgentOrchestrator(
        session_id=session_id,
        project_id=project.id,
        ws_send=ws_send,
    )

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")
            logger.info("[chat] Received message type=%s session=%s", msg_type, session_id)

            if msg_type == "message":
                user_content: str = data["content"]
                selected_model: str | None = data.get("model")
                package_id: str | None = None
                if "packageId" in data and data["packageId"] is not None:
                    package_id = str(data["packageId"])
                logger.info("[chat] User message (%d chars): %.100s...", len(user_content), user_content)

                # Save user message
                await save_message(project.id, "user", user_content)

                # Delegate to orchestrator
                try:
                    await orchestrator.handle_message(user_content, model=selected_model, package_id=package_id)
                except Exception:
                    logger.exception("[chat] Orchestrator error for session %s", session_id)
                    await websocket.send_json({"type": "error", "message": "AI processing failed"})

            elif msg_type == "plan_response":
                action = data.get("action", "reject")
                feedback = data.get("feedback")
                logger.info("[chat] Plan response: action=%s session=%s", action, session_id)

                try:
                    await orchestrator.handle_plan_response(action, feedback)
                except Exception:
                    logger.exception("[chat] Plan response error for session %s", session_id)
                    await websocket.send_json({"type": "error", "message": "Plan handling failed"})

            elif msg_type == "fix_error":
                error_message = data.get("error_message", "")
                error_file = data.get("error_file")
                error_line = data.get("error_line")
                error_stack = data.get("error_stack")
                selected_model = data.get("model")
                logger.info("[chat] Fix error request: file=%s session=%s", error_file, session_id)

                # Save user message with agent card
                card_data = {
                    "type": "error_fix_request",
                    "errorMessage": error_message,
                    "errorFile": error_file,
                    "errorLine": error_line,
                    "errorStack": error_stack,
                }
                # Serialize as HTML comment for parsing on reload
                card_content = f"<!--agent-card:{json.dumps(card_data)}-->"
                await save_message(project.id, "user", card_content)

                try:
                    await orchestrator.handle_fix_error(
                        error_message=error_message,
                        error_file=error_file,
                        error_line=error_line,
                        error_stack=error_stack,
                        model=selected_model,
                    )
                except Exception:
                    logger.exception("[chat] Fix error handling failed for session %s", session_id)
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
