"""WebSocket endpoint that watches the dev server log for errors."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from flow44.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Vite / TypeScript error patterns
# ---------------------------------------------------------------------------

# Vite error banner:  ERROR  ...
# Strip ANSI escape codes for pattern matching
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

_VITE_ERROR_START = re.compile(r"\[vite\].*(?:error|ERROR)|ERROR\s+")

# TypeScript-style error:  src/App.tsx(12,5): error TS2304: ...
_TS_ERROR = re.compile(r"(?P<file>[^\s(]+)\((?P<line>\d+),(?P<col>\d+)\):\s*error\s+\w+:\s*(?P<msg>.+)")

# Vite / esbuild / SWC style:  /path/to/file.tsx:12:5
_FILE_LINE_COL = re.compile(r"(?P<file>/[^\s:]+\.\w+):(?P<line>\d+):(?P<col>\d+)")

# Generic "error" or "Error" on a line (fallback)
_GENERIC_ERROR = re.compile(r"(?:error|Error|ERROR)[:\s]")


def _parse_error_block(block: str) -> dict[str, Any] | None:
    """Try to extract structured error info from a block of log text."""
    # Try TS-style first
    m = _TS_ERROR.search(block)
    if m:
        return {
            "source": "build",
            "message": m.group("msg").strip(),
            "file": m.group("file"),
            "line": int(m.group("line")),
            "column": int(m.group("col")),
        }

    # Try file:line:col style
    m = _FILE_LINE_COL.search(block)
    if m:
        # Extract the error message — usually on the same or next line
        msg_lines = []
        for line in block.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("at ") and not _FILE_LINE_COL.match(stripped):
                msg_lines.append(stripped)
        message = " ".join(msg_lines[:3]) if msg_lines else block.strip()[:200]
        return {
            "source": "build",
            "message": message,
            "file": m.group("file"),
            "line": int(m.group("line")),
            "column": int(m.group("col")),
        }

    # Fallback: generic error
    first_line = block.strip().splitlines()[0] if block.strip() else block
    return {
        "source": "build",
        "message": first_line.strip()[:300],
    }


@router.websocket("/ws/errors/{project_id}")
async def errors_ws(websocket: WebSocket, project_id: str) -> None:  # noqa: C901, PLR0915
    """Watch ``.dev-server.log`` for error patterns and send structured events.

    Sends JSON messages::

        {"source": "build", "message": "...", "file": "...", "line": 12, "column": 5}
    """
    sandbox = sandbox_manager.get_sandbox(project_id)
    if sandbox is None:
        await websocket.close(code=1008, reason="No sandbox")
        return

    log_path = os.path.join(sandbox.workspace_dir, ".dev-server.log")

    await websocket.accept()

    stop = asyncio.Event()
    sent_errors: set[str] = set()  # dedup by message+file

    async def _watch() -> None:  # noqa: C901, PLR0912
        # Wait for the log file to appear
        while not os.path.exists(log_path):  # noqa: ASYNC240
            if stop.is_set():
                return
            await asyncio.sleep(0.5)

        with open(log_path, encoding="utf-8", errors="replace") as f:  # noqa: ASYNC230
            buffer = ""
            while not stop.is_set():
                data = f.read(8192)
                if data:
                    buffer += data
                    # Process complete lines
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        # Strip ANSI codes for pattern matching
                        clean = _ANSI_RE.sub("", line)
                        if (
                            _VITE_ERROR_START.search(clean)
                            or _TS_ERROR.search(clean)
                            or (_GENERIC_ERROR.search(clean) and _FILE_LINE_COL.search(clean))
                        ):
                            # Collect a few more lines for context
                            await asyncio.sleep(0.1)
                            extra = f.read(2048)
                            if extra:
                                buffer = extra + buffer
                            # Grab the error block (strip ANSI for parsing)
                            block = clean
                            for ctx_line in buffer.split("\n")[:5]:
                                block += "\n" + _ANSI_RE.sub("", ctx_line)
                            parsed = _parse_error_block(block)
                            if parsed:
                                dedup_key = f"{parsed.get('message', '')}:{parsed.get('file', '')}"
                                if dedup_key not in sent_errors:
                                    sent_errors.add(dedup_key)
                                    try:
                                        await websocket.send_text(json.dumps(parsed))
                                    except Exception:
                                        return
                else:
                    # Clear dedup cache periodically so new occurrences of
                    # the same error (after a rebuild) are reported
                    if sent_errors:
                        sent_errors.clear()
                    await asyncio.sleep(0.5)

    watch_task = asyncio.create_task(_watch())

    try:
        while True:
            # Accept client messages (runtime errors forwarded from frontend)
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                if data.get("source") == "runtime":
                    # Re-broadcast runtime errors (client → server → client)
                    # This allows future server-side logging/analysis
                    logger.info(
                        "[errors] Runtime error in session %s: %s",
                        project_id,
                        data.get("message", "")[:200],
                    )
            except (json.JSONDecodeError, TypeError):
                pass
    except WebSocketDisconnect:
        pass  # noqa: S110 — expected on client disconnect
    except Exception:
        logger.debug("Error WebSocket failed for session %s", project_id)
    finally:
        stop.set()
        watch_task.cancel()
        try:
            await watch_task
        except asyncio.CancelledError:
            pass
