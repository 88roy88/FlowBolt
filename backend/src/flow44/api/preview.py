"""Preview management and reverse proxy endpoint.

Vite is configured with ``base: '/api/preview/{project_id}/proxy/'`` so all
generated asset paths already include the proxy prefix.  The proxy is a simple
passthrough — no response rewriting required.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from flow44.api.auth import ProjectDep
from flow44.api.sandbox import SandboxDep, WsSandboxDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/preview", tags=["preview"])


@router.get("/{project_id}/port")
async def get_preview_port(project: ProjectDep, sandbox: SandboxDep) -> dict[str, str | int]:
    """Return the allocated port for the sandbox's dev server."""
    return {"project_id": project.id, "port": sandbox.port}


# ---------------------------------------------------------------------------
# Proxy endpoint
# ---------------------------------------------------------------------------


@router.api_route(
    "/{project_id}/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy_to_sandbox(  # noqa: E501
    project: ProjectDep, path: str, request: Request, sandbox: SandboxDep
) -> Response:
    """Reverse proxy requests to the sandbox's dev server.

    Vite serves content under its ``base`` path, so the proxy forwards the
    full prefixed path to the upstream server.
    """

    proxy_prefix = f"/api/preview/{project.id}/proxy"
    target_url = f"http://127.0.0.1:{sandbox.port}{proxy_prefix}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Forward headers, strip hop-by-hop
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
            content="<html><body style='font-family:system-ui;color:#888;display:flex;align-items:center;"
            "justify-content:center;height:100vh;margin:0'>Dev server not running yet. "
            "Wait for <code>pnpm dev</code> to start.</body></html>",
            status_code=503,
            media_type="text/html",
        )
    except Exception:
        logger.exception("Preview proxy error for session %s", project.id)
        raise HTTPException(status_code=502, detail="Preview proxy error") from None

    # Forward response headers
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
async def proxy_ws(websocket: WebSocket, project_id: str, sandbox: WsSandboxDep) -> None:  # noqa: C901
    """Proxy WebSocket connections for Vite HMR."""
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
