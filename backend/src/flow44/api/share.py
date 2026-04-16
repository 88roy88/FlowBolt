"""Public share route: serve a published app by its custom slug."""

import logging

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from flow44.config import settings
from flow44.db.project import get_project_by_slug

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/share", tags=["share"])


@router.get("/{slug}", response_class=HTMLResponse)
async def serve_published_by_slug(slug: str) -> HTMLResponse:
    """Look up a project by its published slug and proxy the HTML from S3."""
    project = await get_project_by_slug(slug)
    if not project or not project.published_url:
        raise HTTPException(status_code=404, detail=f"No published app found for slug '{slug}'.")

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(project.published_url, timeout=15.0)
            resp.raise_for_status()

            headers = {"Cache-Control": f"public, max-age={settings.S3_CACHE_TTL}, must-revalidate"}
            if "etag" in resp.headers:
                headers["ETag"] = resp.headers["etag"]
            if "last-modified" in resp.headers:
                headers["Last-Modified"] = resp.headers["last-modified"]

            return HTMLResponse(content=resp.text, headers=headers)
        except Exception:
            logger.exception("Failed to fetch published app for slug %s from %s", slug, project.published_url)
            raise HTTPException(status_code=502, detail="Error fetching published app from S3.") from None
