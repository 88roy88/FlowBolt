"""WebSocket endpoint for AI chat interactions."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ai.parser import ActionParser
from app.ai.prompts import get_system_prompt
from app.ai.provider import stream_chat
from app.config import settings
from app.models.chat import get_messages, save_message
from app.models.project import get_project_by_session
from app.sandbox.filesystem import write_file
from app.sandbox.nsjail import exec_in_sandbox

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/chat/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: str) -> None:
    """Bidirectional WebSocket for chat.

    Client sends::

        {"type": "message", "content": "user prompt text"}

    Server sends a stream of::

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

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            logger.info("[chat] Received message type=%s session=%s", data.get("type"), session_id)

            if data.get("type") != "message":
                continue

            user_content: str = data["content"]
            logger.info("[chat] User message (%d chars): %.100s...", len(user_content), user_content)

            # 1. Save user message
            await save_message(project.id, "user", user_content)

            # 2. Build conversation context
            history = await get_messages(project.id)
            messages = [{"role": m.role, "content": m.content} for m in history]
            logger.info("[chat] Conversation context: %d messages", len(messages))

            # 3. Stream AI response & parse actions
            full_response: list[str] = []
            pending_files: list[tuple[str, str]] = []
            pending_shells: list[str] = []

            parser = ActionParser(
                on_text=lambda t: None,  # text tracked via full_response
                on_file_action=lambda p, c: pending_files.append((p, c)),
                on_shell_action=lambda c: pending_shells.append(c),
            )

            selected_model: str | None = data.get("model")
            logger.info("[chat] Starting AI stream (model=%s)", selected_model or settings.AI_MODEL)
            chunk_count = 0

            try:
                async for chunk in stream_chat(messages, get_system_prompt(), model=selected_model):
                    chunk_count += 1
                    full_response.append(chunk)
                    parser.feed(chunk)

                    # Send text chunk to client
                    await websocket.send_json({"type": "text", "content": chunk})

                    # Process completed file actions
                    for path, content in pending_files:
                        logger.info("[chat] File action: %s (%d bytes)", path, len(content))
                        await write_file(session_id, path, content)
                        await websocket.send_json({"type": "file", "path": path, "content": content})
                    pending_files.clear()

                    # Process completed shell actions
                    for command in pending_shells:
                        logger.info("[chat] Shell action: %s", command)
                        async for line in exec_in_sandbox(session_id, command):
                            await websocket.send_json(
                                {"type": "shell_output", "command": command, "output": line}
                            )
                    pending_shells.clear()

            except Exception:
                logger.exception("[chat] Error during AI streaming after %d chunks", chunk_count)
                await websocket.send_json({"type": "error", "message": "AI streaming failed"})
                continue

            logger.info("[chat] AI stream complete: %d chunks received", chunk_count)

            parser.flush()

            # Process any remaining actions after flush
            for path, content in pending_files:
                logger.info("[chat] File action (flush): %s", path)
                await write_file(session_id, path, content)
                await websocket.send_json({"type": "file", "path": path, "content": content})
            for command in pending_shells:
                logger.info("[chat] Shell action (flush): %s", command)
                async for line in exec_in_sandbox(session_id, command):
                    await websocket.send_json(
                        {"type": "shell_output", "command": command, "output": line}
                    )

            # 4. Save assistant message
            assistant_content = "".join(full_response)
            await save_message(project.id, "assistant", assistant_content)
            logger.info("[chat] Saved assistant message (%d chars)", len(assistant_content))

            # 5. Signal completion
            await websocket.send_json({"type": "action_complete"})
            logger.info("[chat] action_complete sent for session %s", session_id)

    except WebSocketDisconnect:
        logger.info("[chat] WebSocket disconnected for session %s", session_id)
    except Exception:
        logger.exception("[chat] Unhandled error in chat WebSocket for session %s", session_id)
        try:
            await websocket.send_json({"type": "error", "message": "Internal server error"})
            await websocket.close()
        except Exception:
            pass
