"""WebSocket endpoint that streams the dev server log file."""

from __future__ import annotations

import asyncio
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from flow44.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/server-log/{session_id}")
async def server_log_ws(websocket: WebSocket, session_id: str) -> None:
    """Stream ``.dev-server.log`` to the client.

    Reads the file in binary mode so ANSI color codes are preserved.
    The xterm frontend renders them natively.
    """
    sandbox = sandbox_manager.get_sandbox(session_id)
    if sandbox is None:
        await websocket.close(code=1008, reason="No sandbox")
        return

    log_path = os.path.join(sandbox.workspace_dir, ".dev-server.log")

    await websocket.accept()

    stop = asyncio.Event()

    async def _tail() -> None:
        """Read existing content then poll for new data."""
        while not os.path.exists(log_path):
            if stop.is_set():
                return
            await asyncio.sleep(0.5)

        with open(log_path, "rb") as f:
            while not stop.is_set():
                data = f.read(8192)
                if data:
                    try:
                        await websocket.send_bytes(data)
                    except Exception:
                        return
                else:
                    await asyncio.sleep(0.3)

    tail_task = asyncio.create_task(_tail())

    try:
        # Keep the connection alive by consuming client messages (pings/close)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        stop.set()
        tail_task.cancel()
        try:
            await tail_task
        except asyncio.CancelledError:
            pass
