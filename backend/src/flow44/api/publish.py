"""REST endpoint for publishing a project to S3."""

from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from flow44.api.export import build_single_html
from flow44.config import settings
from flow44.db.project import get_project, update_project_published_url
from flow44.integrations.s3 import deploy_single_html
from flow44.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export/{project_id}", tags=["publish"])


@router.post("/publish")
async def publish_to_s3(project_id: str) -> dict[str, str]:
    """Build the project and deploy to S3, returning the public URL."""
    sandbox = sandbox_manager.get_sandbox(project_id)
    if sandbox is None:
        raise HTTPException(status_code=404, detail=f"No sandbox found for project {project_id}")

    # Ensure the bucket exists with public-read policy
    if settings.S3_BUCKET_NAME is None or settings.S3_BUCKET_NAME == "":
        logger.error("S3_BUCKET_NAME environment variable is not set")
        raise HTTPException(status_code=500, detail="S3_BUCKET_NAME is not set")

    # Build a single HTML string containing the entire app with inline assets
    html_content = await build_single_html(project_id)

    # Deploy the single HTML to S3 securely without blocking the event loop
    try:
        loop = asyncio.get_running_loop()
        s3_url = await loop.run_in_executor(None, deploy_single_html, html_content, project_id)
    except Exception as exc:
        logger.exception("S3 deployment failed for project %s", project_id)
        raise HTTPException(status_code=502, detail=f"S3 deployment failed: {exc}") from exc

    await update_project_published_url(project_id, s3_url)

    base_url = settings.EXPORT_API_BASE_URL
    proxy_url = f"{base_url}/api/export/{project_id}/published"

    project = await get_project(project_id)
    project_name = project.name if project else project_id

    logger.info("Published project '%s' (id %s) to %s (proxy: %s)", project_name, project_id, s3_url, proxy_url)

    return {"url": proxy_url, "project_name": project_name}


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
            headers = {"Cache-Control": "public, max-age=0, must-revalidate"}
            if "etag" in resp.headers:
                headers["ETag"] = resp.headers["etag"]
            if "last-modified" in resp.headers:
                headers["Last-Modified"] = resp.headers["last-modified"]

            return HTMLResponse(content=resp.text, headers=headers)
        except Exception:
            logger.exception("Failed to fetch published app for project %s from %s", project_id, project.published_url)
            raise HTTPException(status_code=502, detail="Error fetching published app from S3.") from None
