"""Preview management and reverse proxy endpoint.

Vite is configured with ``base: '/api/preview/{project_id}/proxy/'`` so all
generated asset paths already include the proxy prefix.  The proxy is a simple
passthrough — no response rewriting required.
"""

from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from flow44.api.deps import SandboxDep, get_ws_sandbox
from flow44.sandbox.main import PnpmSandbox
from flow44.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/preview", tags=["preview"])

_WAKING_UP_HTML = """\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Waking up...</title></head>
<body style="font-family:system-ui;color:#666;display:flex;align-items:center;\
justify-content:center;height:100vh;margin:0;flex-direction:column;gap:12px;\
background:#fafafa">
<div style="font-size:1.2rem">Waking up project...</div>
<div style="font-size:0.85rem;color:#999">This usually takes a few seconds.</div>
<script>setTimeout(()=>location.reload(),3000)</script>
</body>
</html>
"""


@router.get("/{project_id}/port")
async def get_preview_port(project_id: str, sandbox: Annotated[PnpmSandbox, SandboxDep]) -> dict[str, str | int]:
    """Return the allocated port for the sandbox's dev server."""
    return {"project_id": project_id, "port": sandbox.port}


# ---------------------------------------------------------------------------
# Proxy endpoint
# ---------------------------------------------------------------------------


@router.api_route(
    "/{project_id}/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy_to_sandbox(project_id: str, path: str, request: Request) -> Response:
    """Reverse proxy requests to the sandbox's dev server.

    Vite serves content under its ``base`` path, so the proxy forwards the
    full prefixed path to the upstream server.

    If the sandbox was evicted (idle), this triggers re-creation and shows
    a "waking up" page that auto-retries after 3 seconds.
    """
    sandbox = await sandbox_manager.get_or_create_sandbox(project_id)

    if not sandbox.is_dev_server_running():
        await sandbox_manager.ensure_ready(sandbox)
        return Response(
            content=_WAKING_UP_HTML,
            status_code=503,
            media_type="text/html",
            headers={"Cache-Control": "no-store", "Retry-After": "3"},
        )

    proxy_prefix = f"/api/preview/{project_id}/proxy"
    target_url = f"http://127.0.0.1:{sandbox.port}{proxy_prefix}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    headers = dict(request.headers)
    for h in ("host", "connection", "transfer-encoding"):
        headers.pop(h, None)

    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body if body else None,
            )
    except httpx.ConnectError:
        return Response(
            content=_WAKING_UP_HTML,
            status_code=503,
            media_type="text/html",
            headers={"Cache-Control": "no-store", "Retry-After": "3"},
        )
    except Exception:
        logger.exception("Preview proxy error for session %s", project_id)
        raise HTTPException(status_code=502, detail="Preview proxy error") from None

    response_headers = dict(resp.headers)
    for h in ("content-encoding", "content-length", "transfer-encoding", "connection"):
        response_headers.pop(h, None)

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=response_headers,
        media_type=resp.headers.get("content-type"),
    )


# ---------------------------------------------------------------------------
# WebSocket proxy for Vite HMR
# ---------------------------------------------------------------------------


@router.websocket("/{project_id}/proxy/")
@router.websocket("/{project_id}/proxy")
async def proxy_ws(websocket: WebSocket, project_id: str) -> None:  # noqa: C901
    """Proxy WebSocket connections for Vite HMR."""
    sandbox = await get_ws_sandbox(websocket, project_id)
    if sandbox is None:
        return

    await websocket.accept()

    import asyncio  # noqa: PLC0415

    import websockets  # noqa: PLC0415

    proxy_prefix = f"/api/preview/{project_id}/proxy"
    query = websocket.scope.get("query_string", b"").decode()
    target_url = f"ws://127.0.0.1:{sandbox.port}{proxy_prefix}"
    if query:
        target_url += f"?{query}"

    try:
        async with websockets.connect(target_url) as upstream:

            async def client_to_upstream() -> None:
                try:
                    while True:
                        data = await websocket.receive_text()
                        await upstream.send(data)
                except WebSocketDisconnect:
                    pass

            async def upstream_to_client() -> None:
                try:
                    async for msg in upstream:
                        await websocket.send_text(str(msg))
                except Exception:
                    logger.debug("HMR upstream→client relay ended")

            await asyncio.gather(client_to_upstream(), upstream_to_client())
    except Exception:
        logger.debug("HMR WebSocket proxy failed for session %s", project_id)
    finally:
        try:
            await websocket.close()
        except Exception:
            logger.debug("HMR WebSocket close failed")
