from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from flow44.api.deps import get_ws_sandbox
from flow44.sandbox.pty import PtyHandle

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/terminal/{project_id}")
async def terminal_ws(websocket: WebSocket, project_id: str) -> None:  # noqa: C901
    sandbox = await get_ws_sandbox(websocket, project_id)
    if sandbox is None:
        return

    await websocket.accept()

    pty: PtyHandle | None = None
    try:
        pty = sandbox.get_or_create_pty()
    except Exception:
        logger.exception("Failed to create PTY for session %s", project_id)
        await websocket.close(code=1011, reason="Failed to create terminal")
        return

    # Replay scrollback so the client sees recent terminal history.
    scrollback = pty.get_scrollback()
    if scrollback:
        try:
            await websocket.send_bytes(scrollback)
        except Exception:
            logger.debug("Failed to send scrollback for session %s", project_id)

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
        logger.info("Terminal WebSocket disconnected for session %s", project_id)
    except Exception:
        logger.exception("Error in terminal WebSocket for session %s", project_id)
    finally:
        # Detach only — do NOT kill the PTY. It stays alive for reconnection.
        stop_event.set()
        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass
