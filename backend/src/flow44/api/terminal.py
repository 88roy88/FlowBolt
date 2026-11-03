from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException

from flow44.api.deps import (
    Permission,
    WsProjectDep,
    WsSandboxDep,
    WsUserDep,
    can_use_terminal,
    require_ws_permission,
)
from flow44.sandbox.pty import BasePTY

logger = logging.getLogger(__name__)

router = APIRouter()


async def _send_scrollback(websocket: WebSocket, pty: BasePTY, project_id: str) -> None:
    """Replay scrollback so the client sees recent terminal history.

    It is sent as a text frame so the client can tell it apart from live output: terminal
    queries in it (e.g. device attributes) were already answered and must not be answered again.
    """
    scrollback = pty.get_scrollback()
    if not scrollback:
        return
    try:
        text = scrollback.decode("utf-8", errors="replace")
        await websocket.send_text(json.dumps({"type": "scrollback", "data": text}))
    except Exception:
        logger.debug("Failed to send scrollback for session %s", project_id)


def _handle_control(pty: BasePTY, text: str) -> None:
    try:
        msg = json.loads(text)
    except ValueError:
        return
    if isinstance(msg, dict) and msg.get("type") == "resize":
        rows, cols = msg.get("rows"), msg.get("cols")
        if isinstance(rows, int) and isinstance(cols, int) and rows > 0 and cols > 0:
            try:
                pty.resize(rows, cols)
            except Exception:
                logger.debug("Failed to resize PTY", exc_info=True)


@router.websocket("/ws/terminal/{project_id}")
async def terminal_ws(  # noqa: C901
    websocket: WebSocket,
    user_id: WsUserDep,
    project: WsProjectDep,
    sandbox: WsSandboxDep,
    _perms: set[Permission] = require_ws_permission(Permission.write),
) -> None:
    if not can_use_terminal(user_id):
        raise WebSocketException(code=4403, reason="Terminal is not available")

    await websocket.accept()

    pty: BasePTY | None = None
    try:
        pty = sandbox.get_or_create_pty()
    except Exception:
        logger.exception("Failed to create PTY for session %s", project.id)
        await websocket.close(code=1011, reason="Failed to create terminal")
        return

    await _send_scrollback(websocket, pty, project.id)

    stop_event = asyncio.Event()

    async def _reader() -> None:
        loop = asyncio.get_running_loop()
        while not stop_event.is_set():
            try:
                data = await loop.run_in_executor(None, pty.read)
                if data:
                    await websocket.send_bytes(data)
                else:
                    await asyncio.sleep(0.01)
            except Exception:
                break

    reader_task = asyncio.create_task(_reader())

    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))
            # Binary frames are keyboard input; text frames are JSON control messages.
            if message.get("bytes") is not None:
                pty.write(message["bytes"])
            elif message.get("text") is not None:
                _handle_control(pty, message["text"])
    except WebSocketDisconnect:
        logger.info("Terminal WebSocket disconnected for session %s", project.id)
    except Exception:
        logger.exception("Error in terminal WebSocket for session %s", project.id)
    finally:
        # Detach only — do NOT kill the PTY. It stays alive for reconnection.
        stop_event.set()
        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass
