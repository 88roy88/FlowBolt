"""Preview management and reverse proxy endpoint."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/preview", tags=["preview"])


@router.get("/{session_id}/port")
async def get_preview_port(session_id: str):
    """Return the allocated port for the sandbox's dev server."""
    sandbox = sandbox_manager.get_sandbox(session_id)
    if sandbox is None:
        raise HTTPException(status_code=404, detail="No sandbox found for this session")
    return {"session_id": session_id, "port": sandbox.port}


@router.api_route(
    "/{session_id}/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy_to_sandbox(session_id: str, path: str, request: Request):
    """Reverse proxy requests to the sandbox's dev server.

    This allows the preview iframe at /preview/{session_id}/ to load the
    application running inside the sandbox.
    """
    sandbox = sandbox_manager.get_sandbox(session_id)
    if sandbox is None:
        raise HTTPException(status_code=404, detail="No sandbox found for this session")

    target_url = f"http://127.0.0.1:{sandbox.port}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Forward headers, strip hop-by-hop
    headers = dict(request.headers)
    for h in ("host", "connection", "transfer-encoding"):
        headers.pop(h, None)

    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body if body else None,
            )
    except httpx.ConnectError:
        return Response(
            content="<html><body style='font-family:system-ui;color:#888;display:flex;align-items:center;"
            "justify-content:center;height:100vh;margin:0'>Dev server not running yet. "
            "Wait for <code>pnpm dev</code> to start.</body></html>",
            status_code=503,
            media_type="text/html",
        )
    except Exception:
        logger.exception("Preview proxy error for session %s", session_id)
        raise HTTPException(status_code=502, detail="Preview proxy error")

    # Forward response, preserving content type
    response_headers = dict(resp.headers)
    for h in ("content-encoding", "content-length", "transfer-encoding", "connection"):
        response_headers.pop(h, None)

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=response_headers,
        media_type=resp.headers.get("content-type"),
    )
