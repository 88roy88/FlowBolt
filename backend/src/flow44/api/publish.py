import asyncio
import logging

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from flow44.api.auth import ProjectDep
from flow44.config import settings
from flow44.db.project import update_project_published_url
from flow44.integrations.s3 import deploy_single_html
from flow44.sandbox.operations import BuildError, build_single_html

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export/{project_id}", tags=["publish"])


@router.post("/publish")
async def publish_to_s3(project: ProjectDep) -> dict[str, str]:
    """Build the project and deploy to S3, returning the public URL."""

    # Ensure the bucket exists with public-read policy
    if settings.S3_BUCKET_NAME is None:
        logger.error("S3_BUCKET_NAME environment variable is not set")
        raise HTTPException(status_code=500, detail="S3_BUCKET_NAME is not set")

    # Build a single HTML string containing the entire app with inline assets
    try:
        html_content = await build_single_html(project.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BuildError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Deploy the single HTML to S3 securely without blocking the event loop
    try:
        loop = asyncio.get_running_loop()
        s3_url = await loop.run_in_executor(None, deploy_single_html, html_content, project.id)
    except Exception as exc:
        logger.exception("S3 deployment failed for project %s", project.id)
        raise HTTPException(status_code=502, detail=f"S3 deployment failed: {exc}") from exc

    await update_project_published_url(project.id, s3_url)

    proxy_path = f"/api/export/{project.id}/published"
    logger.info("Published project %s to %s (proxy: %s)", project.id, s3_url, proxy_path)

    return {"url": proxy_path}


@router.get("/published", response_class=HTMLResponse)
async def proxy_published_app(project: ProjectDep) -> HTMLResponse:
    """Proxy route to fetch and serve the published HTML from S3."""
    if not project.published_url:
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
            logger.exception("Failed to fetch published app for project %s from %s", project.id, project.published_url)
            raise HTTPException(status_code=502, detail="Error fetching published app from S3.") from None
