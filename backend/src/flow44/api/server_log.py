"""WebSocket endpoint that streams the dev server log file."""

from __future__ import annotations

import asyncio
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from flow44.api.sandbox import accept_ws_sandbox

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/server-log/{project_id}")
async def server_log_ws(websocket: WebSocket, project_id: str) -> None:  # noqa: C901
    """Stream ``.dev-server.log`` to the client.

    Reads the file in binary mode so ANSI color codes are preserved.
    The xterm frontend renders them natively.
    """
    sandbox = await accept_ws_sandbox(websocket, project_id)
    if sandbox is None:
        return

    log_path = os.path.join(sandbox.workspace_dir, ".dev-server.log")

    stop = asyncio.Event()

    async def _tail() -> None:
        """Read existing content then poll for new data."""
        while not os.path.exists(log_path):  # noqa: ASYNC240
            if stop.is_set():
                return
            await asyncio.sleep(0.5)

        with open(log_path, "rb") as f:  # noqa: ASYNC230
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
        pass  # noqa: S110 — expected on client disconnect
    except Exception:
        logger.debug("Server log WebSocket error for session %s", project_id)
    finally:
        stop.set()
        tail_task.cancel()
        try:
            await tail_task
        except asyncio.CancelledError:
            pass
