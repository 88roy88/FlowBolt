from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.sandbox.pty import PtyHandle
from app.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/terminal/{session_id}")
async def terminal_ws(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()

    sandbox = sandbox_manager.get_sandbox(session_id)
    if sandbox is None:
        await websocket.close(code=1008, reason="No sandbox")
        return

    pty: PtyHandle | None = None
    try:
        pty = sandbox.get_or_create_pty()
    except Exception:
        logger.exception("Failed to create PTY for session %s", session_id)
        await websocket.close(code=1011, reason="Failed to create terminal")
        return

    # Replay scrollback so the client sees recent terminal history.
    scrollback = pty.get_scrollback()
    if scrollback:
        try:
            await websocket.send_bytes(scrollback)
        except Exception:
            pass

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
            data = await websocket.receive_bytes()
            pty.write(data)
    except WebSocketDisconnect:
        logger.info("Terminal WebSocket disconnected for session %s", session_id)
    except Exception:
        logger.exception("Error in terminal WebSocket for session %s", session_id)
    finally:
        # Detach only — do NOT kill the PTY. It stays alive for reconnection.
        stop_event.set()
        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass
