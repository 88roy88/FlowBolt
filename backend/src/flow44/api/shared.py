"""Public serving routes: published apps by project ID or custom slug."""

import logging

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from flow44.config import settings
from flow44.db.project import get_project_by_handle
from flow44.integrations.s3 import get_published_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shared", tags=["shared"])


def _s3_response(html: str, headers_src: httpx.Headers) -> HTMLResponse:
    headers: dict[str, str] = {"Cache-Control": f"public, max-age={settings.S3_CACHE_TTL}, must-revalidate"}
    if "etag" in headers_src:
        headers["ETag"] = headers_src["etag"]
    if "last-modified" in headers_src:
        headers["Last-Modified"] = headers_src["last-modified"]
    return HTMLResponse(content=html, headers=headers)


async def _proxy_from_s3(source_url: str, log_ctx: str) -> HTMLResponse:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(source_url, timeout=15.0)
            resp.raise_for_status()
            return _s3_response(resp.text, resp.headers)
        except Exception:
            logger.exception("Failed to fetch published app for %s from %s", log_ctx, source_url)
            raise HTTPException(status_code=502, detail="Error fetching published app from S3.") from None


@router.get("/{handle}", response_class=HTMLResponse)
async def serve_published_app(handle: str) -> HTMLResponse:
    """Serve a published app via its custom slug or project ID handle."""
    project = await get_project_by_handle(handle)
    if not project or not project.published_at:
        raise HTTPException(status_code=404, detail=f"No published app found for handle '{handle}'.")

    source_url = get_published_url(project.id)
    return await _proxy_from_s3(source_url, f"handle {handle}")
