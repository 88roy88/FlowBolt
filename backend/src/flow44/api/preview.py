import logging

import httpx
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from flow44.api.deps import ProjectDep, SandboxDep, WsProjectDep, WsSandboxDep
from flow44.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/preview", tags=["preview"])

_proxy_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)


def _loading_page(title: str, message: str, detail: str, reload_ms: int) -> str:
    return (
        f'<!DOCTYPE html>\n<html>\n<head><meta charset="utf-8"><title>{title}</title></head>\n'
        f'<body style="font-family:system-ui;color:#666;display:flex;align-items:center;'
        f"justify-content:center;height:100vh;margin:0;flex-direction:column;gap:12px;"
        f'background:#fafafa">\n'
        f'<div style="font-size:1.2rem">{message}</div>\n'
        f'<div style="font-size:0.85rem;color:#999">{detail}</div>\n'
        f"<script>setTimeout(()=>location.reload(),{reload_ms})</script>\n"
        f"</body>\n</html>\n"
    )


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
async def proxy_to_sandbox(
    project: ProjectDep,
    path: str,
    request: Request,
) -> Response:
    sandbox = await sandbox_manager.wake_sandbox(project.id)

    if not sandbox.is_dev_server_running():
        return Response(
            content=_loading_page(
                "Preparing...",
                "Preparing project environment...",
                "Installing dependencies. This may take up to a minute.",
                5000,
            ),
            status_code=503,
            media_type="text/html",
            headers={"Cache-Control": "no-store", "Retry-After": "5"},
        )

    proxy_prefix = f"/api/preview/{project.id}/proxy"
    target_url = f"http://127.0.0.1:{sandbox.port}{proxy_prefix}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    headers = dict(request.headers)
    for h in ("host", "connection", "transfer-encoding"):
        headers.pop(h, None)

    body = await request.body()

    try:
        resp = await _proxy_client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body if body else None,
        )
    except httpx.ConnectError:
        return Response(
            content=_loading_page(
                "Waking up...",
                "Waking up project...",
                "This usually takes a few seconds.",
                3000,
            ),
            status_code=503,
            media_type="text/html",
            headers={"Cache-Control": "no-store", "Retry-After": "3"},
        )
    except Exception:
        logger.exception("Preview proxy error for session %s", project.id)
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
async def proxy_ws(websocket: WebSocket, project: WsProjectDep, sandbox: WsSandboxDep) -> None:
    """Proxy WebSocket connections for Vite HMR."""
    await websocket.accept()

    import asyncio  # noqa: PLC0415

    import websockets  # noqa: PLC0415

    proxy_prefix = f"/api/preview/{project.id}/proxy"
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
        logger.debug("HMR WebSocket proxy failed for session %s", project.id)
    finally:
        try:
            await websocket.close()
        except Exception:
            logger.debug("HMR WebSocket close failed")
