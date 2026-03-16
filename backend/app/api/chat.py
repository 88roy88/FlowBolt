"""WebSocket endpoint for AI chat interactions."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ai.parser import ActionParser
from app.ai.prompts import get_system_prompt
from app.ai.provider import stream_chat
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

    project = await get_project_by_session(session_id)
    if project is None:
        await websocket.send_json({"type": "error", "message": "Unknown session"})
        await websocket.close()
        return

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            if data.get("type") != "message":
                continue

            user_content: str = data["content"]

            # 1. Save user message
            await save_message(project.id, "user", user_content)

            # 2. Build conversation context
            history = await get_messages(project.id)
            messages = [{"role": m.role, "content": m.content} for m in history]

            # 3. Stream AI response & parse actions
            full_response: list[str] = []

            async def _handle_text(text: str) -> None:
                await websocket.send_json({"type": "text", "content": text})

            async def _handle_file(path: str, content: str) -> None:
                await write_file(session_id, path, content)
                await websocket.send_json({"type": "file", "path": path, "content": content})

            async def _handle_shell(command: str) -> None:
                output_parts: list[str] = []
                async for line in exec_in_sandbox(session_id, command):
                    output_parts.append(line)
                    await websocket.send_json(
                        {"type": "shell_output", "command": command, "output": line}
                    )

            # We need synchronous callbacks for the parser but async operations
            # inside them.  Collect actions and execute after each chunk batch.
            pending_files: list[tuple[str, str]] = []
            pending_shells: list[str] = []

            parser = ActionParser(
                on_text=lambda t: full_response.append(t),
                on_file_action=lambda p, c: pending_files.append((p, c)),
                on_shell_action=lambda c: pending_shells.append(c),
            )

            async for chunk in stream_chat(messages, get_system_prompt()):
                full_response.append(chunk)
                parser.feed(chunk)

                # Flush any text that isn't part of an action
                # (The parser calls on_text synchronously so we mirror it here.)
                # Send text chunks directly
                await websocket.send_json({"type": "text", "content": chunk})

                # Process completed actions
                for path, content in pending_files:
                    await _handle_file(path, content)
                pending_files.clear()

                for command in pending_shells:
                    await _handle_shell(command)
                pending_shells.clear()

            parser.flush()

            # Process any remaining actions after flush
            for path, content in pending_files:
                await _handle_file(path, content)
            for command in pending_shells:
                await _handle_shell(command)

            # 4. Save assistant message
            assistant_content = "".join(full_response)
            await save_message(project.id, "assistant", assistant_content)

            # 5. Signal completion
            await websocket.send_json({"type": "action_complete"})

    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected for session %s", session_id)
    except Exception:
        logger.exception("Error in chat WebSocket for session %s", session_id)
        try:
            await websocket.send_json({"type": "error", "message": "Internal server error"})
            await websocket.close()
        except Exception:
            pass
