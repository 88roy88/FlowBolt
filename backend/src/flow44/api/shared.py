"""Public serving routes for shared apps by project ID or custom slug."""

import logging
import mimetypes
import os

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from flow44.config import settings
from flow44.db.project import get_project_by_handle
from flow44.integrations.s3 import get_published_url, get_shared_asset_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shared", tags=["shared"])


def _cache_headers(headers_src: httpx.Headers) -> dict[str, str]:
    headers: dict[str, str] = {"Cache-Control": f"public, max-age={settings.S3_CACHE_TTL}, must-revalidate"}
    if "etag" in headers_src:
        headers["ETag"] = headers_src["etag"]
    if "last-modified" in headers_src:
        headers["Last-Modified"] = headers_src["last-modified"]
    return headers


async def _fetch_first(urls: list[str], log_ctx: str) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        for source_url in urls:
            try:
                resp = await client.get(source_url, timeout=15.0)
                resp.raise_for_status()
                return resp
            except Exception:
                logger.debug("Failed shared object fetch for %s from %s", log_ctx, source_url, exc_info=True)
    raise HTTPException(status_code=502, detail="Error fetching shared app from S3.")


def _is_static_asset(path: str) -> bool:
    return bool(os.path.splitext(path)[1])


async def _serve_shared_path(handle: str, path: str) -> Response:
    project = await get_project_by_handle(handle)
    if not project or not project.published_at:
        raise HTTPException(status_code=404, detail=f"No shared app found for handle '{handle}'.")

    requested_path = path.lstrip("/") or "index.html"
    urls = [get_shared_asset_url(project.id, requested_path)]
    if requested_path == "index.html":
        urls.append(get_published_url(project.id))

    try:
        resp = await _fetch_first(urls, f"handle {handle}, path {requested_path}")
    except HTTPException:
        if _is_static_asset(requested_path):
            raise
        resp = await _fetch_first(
            [get_shared_asset_url(project.id, "index.html"), get_published_url(project.id)],
            f"handle {handle}, SPA fallback",
        )

    headers = _cache_headers(resp.headers)
    if requested_path == "index.html" or not _is_static_asset(requested_path):
        return HTMLResponse(content=resp.text, headers=headers)
    media_type = resp.headers.get("content-type") or mimetypes.guess_type(requested_path)[0]
    return Response(content=resp.content, headers=headers, media_type=media_type)


@router.get("/{handle}", response_class=HTMLResponse)
async def serve_shared_app(handle: str) -> HTMLResponse:
    """Serve a shared app via its custom slug or project ID handle."""
    response = await _serve_shared_path(handle, "index.html")
    if not isinstance(response, HTMLResponse):
        raise HTTPException(status_code=502, detail="Shared index is not HTML.")
    return response


@router.get("/{handle}/{path:path}")
async def serve_shared_asset_or_route(handle: str, path: str) -> Response:
    """Serve a shared asset, or index.html for a client-side route."""
    return await _serve_shared_path(handle, path)
