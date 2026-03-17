"""WebSocket endpoint for interactive PTY terminal sessions."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.sandbox.manager import sandbox_manager
from app.sandbox.pty import PtyProcess, close_pty, create_pty_process, read_pty, write_pty

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/terminal/{session_id}")
async def terminal_ws(websocket: WebSocket, session_id: str) -> None:
    """Bidirectional PTY WebSocket.

    Client sends raw bytes (keystrokes); server sends terminal output bytes.
    The dev server is managed by sandbox_manager as a background process.
    """
    await websocket.accept()

    pty_proc: PtyProcess | None = None
    try:
        pty_proc = create_pty_process(session_id)
    except Exception:
        logger.exception("Failed to create PTY for session %s", session_id)
        await websocket.close(code=1011, reason="Failed to create terminal")
        return

    stop_event = asyncio.Event()

    async def _reader() -> None:
        """Continuously read PTY output and send to the WebSocket client."""
        loop = asyncio.get_running_loop()
        while not stop_event.is_set():
            try:
                data = await loop.run_in_executor(None, read_pty, pty_proc)
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
            write_pty(pty_proc, data)
    except WebSocketDisconnect:
        logger.info("Terminal WebSocket disconnected for session %s", session_id)
    except Exception:
        logger.exception("Error in terminal WebSocket for session %s", session_id)
    finally:
        stop_event.set()
        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass
        if pty_proc is not None:
            close_pty(pty_proc)
