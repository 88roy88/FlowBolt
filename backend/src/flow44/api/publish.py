import asyncio
import logging
import re

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from flow44.config import settings
from flow44.db.project import get_project, is_slug_taken, update_project_published_url
from flow44.integrations.s3 import deploy_single_html
from flow44.sandbox.operations import BuildError, build_single_html

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export/{project_id}", tags=["publish"])

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")


class PublishRequest(BaseModel):
    slug: str | None = None


@router.get("/slug/check")
async def check_slug(project_id: str, slug: str = Query(...)) -> dict[str, bool]:
    """Return whether a slug is available for this project."""
    if not _SLUG_RE.match(slug):
        return {"available": False}
    taken = await is_slug_taken(slug, exclude_project_id=project_id)
    return {"available": not taken}


async def _validate_slug(slug: str, project_id: str) -> None:
    if not _SLUG_RE.match(slug):
        raise HTTPException(
            status_code=400,
            detail="Invalid slug. Use 3–50 lowercase letters, numbers, and hyphens (must start and end with a letter or digit).",
        )
    if await is_slug_taken(slug, exclude_project_id=project_id):
        raise HTTPException(status_code=409, detail=f"The slug '{slug}' is already taken.")


@router.post("/publish")
async def publish_to_s3(project_id: str, body: PublishRequest = PublishRequest()) -> dict[str, str]:
    """Build the project and deploy to S3, returning the public URL."""

    if settings.S3_BUCKET_NAME is None:
        logger.error("S3_BUCKET_NAME environment variable is not set")
        raise HTTPException(status_code=500, detail="S3_BUCKET_NAME is not set")

    slug = body.slug or None
    if slug:
        await _validate_slug(slug, project_id)

    # Build a single HTML string containing the entire app with inline assets
    try:
        html_content = await build_single_html(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BuildError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Deploy the single HTML to S3 securely without blocking the event loop
    try:
        loop = asyncio.get_running_loop()
        s3_url = await loop.run_in_executor(None, deploy_single_html, html_content, project_id)
    except Exception as exc:
        logger.exception("S3 deployment failed for project %s", project_id)
        raise HTTPException(status_code=502, detail=f"S3 deployment failed: {exc}") from exc

    await update_project_published_url(project_id, s3_url, slug=slug)

    public_path = f"/api/share/{slug}" if slug else f"/api/export/{project_id}/published"
    logger.info("Published project %s to %s (public: %s)", project_id, s3_url, public_path)

    return {"url": public_path, "slug": slug or ""}


@router.get("/published", response_class=HTMLResponse)
async def proxy_published_app(project_id: str) -> HTMLResponse:
    """Proxy route to fetch and serve the published HTML from S3."""
    project = await get_project(project_id)
    if not project or not project.published_url:
        raise HTTPException(status_code=404, detail="Published app not found or not published yet.")

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(project.published_url, timeout=15.0)
            resp.raise_for_status()

            # Forward some headers from S3 for better caching behavior
            headers = {"Cache-Control": f"public, max-age={settings.S3_CACHE_TTL}, must-revalidate"}
            if "etag" in resp.headers:
                headers["ETag"] = resp.headers["etag"]
            if "last-modified" in resp.headers:
                headers["Last-Modified"] = resp.headers["last-modified"]

            return HTMLResponse(content=resp.text, headers=headers)
        except Exception:
            logger.exception("Failed to fetch published app for project %s from %s", project_id, project.published_url)
            raise HTTPException(status_code=502, detail="Error fetching published app from S3.") from None
