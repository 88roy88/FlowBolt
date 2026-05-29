"""WebSocket endpoint that watches the dev server log for errors."""

from __future__ import annotations

import asyncio
import json
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from flow44.api.sandbox import WsSandboxDep
from flow44.errors.parser import BuildError, is_error_line, parse_error_block, should_ignore, strip_ansi

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/errors/{project_id}")
async def errors_ws(websocket: WebSocket, project_id: str, sandbox: WsSandboxDep) -> None:  # noqa: C901, PLR0915
    """Watch ``.dev-server.log`` for error patterns and send structured events."""
    await websocket.accept()

    log_path = os.path.join(sandbox.workspace_dir, ".dev-server.log")

    stop = asyncio.Event()
    sent_errors: set[BuildError] = set()

    async def _watch() -> None:  # noqa: C901
        # Wait for the log file to appear
        while not os.path.exists(log_path):  # noqa: ASYNC240
            if stop.is_set():
                return
            await asyncio.sleep(0.5)

        with open(log_path, encoding="utf-8", errors="replace") as f:  # noqa: ASYNC230
            # Seek to end — only report errors that appear after we connect
            f.seek(0, 2)

            buffer = ""
            while not stop.is_set():
                data = f.read(8192)
                if data:
                    buffer += data
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        clean = strip_ansi(line)

                        if should_ignore(clean):
                            continue

                        if is_error_line(clean):
                            # Collect a few more lines for context
                            await asyncio.sleep(0.1)
                            extra = f.read(2048)
                            if extra:
                                buffer = extra + buffer

                            block = clean
                            for ctx_line in buffer.split("\n")[:5]:
                                block += "\n" + strip_ansi(ctx_line)

                            parsed = parse_error_block(block)
                            if parsed and parsed not in sent_errors:
                                sent_errors.add(parsed)
                                try:
                                    await websocket.send_text(json.dumps(parsed.model_dump(exclude_none=True)))
                                except Exception:
                                    return
                else:
                    await asyncio.sleep(0.5)

    watch_task = asyncio.create_task(_watch())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                if data.get("source") == "runtime":
                    logger.info(
                        "[errors] Runtime error in project %s: %s",
                        project_id,
                        data.get("message", "")[:200],
                    )
            except (json.JSONDecodeError, TypeError):
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug("Error WebSocket failed for project %s", project_id)
    finally:
        stop.set()
        watch_task.cancel()
        try:
            await watch_task
        except asyncio.CancelledError:
            pass
