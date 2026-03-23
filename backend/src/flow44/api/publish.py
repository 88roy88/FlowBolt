"""REST endpoint for publishing a project to S3."""

from __future__ import annotations

import logging
import asyncio

from fastapi import APIRouter, HTTPException

from flow44.api.export import build_single_html
from flow44.config import settings
from flow44.integrations.s3 import deploy_single_html, setup_bucket, BUCKET_NAME
from flow44.models.project import get_project_by_session, update_project_published_url_by_session
from flow44.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export/{session_id}", tags=["publish"])


@router.post("/publish")
async def publish_to_s3(session_id: str) -> dict[str, str]:
    """Build the project and deploy to S3, returning the public URL."""
    sandbox = sandbox_manager.get_sandbox(session_id)
    if sandbox is None:
        raise HTTPException(status_code=404, detail=f"No sandbox found for session {session_id}")

    workspace_dir = sandbox.workspace_dir

    # Ensure the bucket exists with public-read policy
    if BUCKET_NAME is None:
        logger.error("S3_BUCKET_NAME environment variable is not set")
        raise HTTPException(status_code=500, detail="S3_BUCKET_NAME is not set")

    bucket: str = BUCKET_NAME
    try:
        setup_bucket(bucket)
    except Exception as exc:
        logger.warning("Bucket setup issue (may already exist): %s", exc)

    # Build a single HTML string containing the entire app with inline assets
    html_content = await build_single_html(session_id)

    # Deploy the single HTML to S3 securely without blocking the event loop
    try:
        loop = asyncio.get_running_loop()
        s3_url = await loop.run_in_executor(None, deploy_single_html, html_content, session_id)
    except Exception as exc:
        logger.exception("S3 deployment failed for session %s", session_id)
        raise HTTPException(status_code=502, detail=f"S3 deployment failed: {exc}")

    # Save the published URL in our database
    await update_project_published_url_by_session(session_id, s3_url)

    # Instead of returning the raw S3 url, we return the proxy url to the frontend
    # Since the frontend accesses the app from the same origin, we can construct
    # the backend URL from settings.
    base_url = settings.EXPORT_API_BASE_URL or "http://localhost:8000"
    proxy_url = f"{base_url}/api/export/{session_id}/published"

    project = await get_project_by_session(session_id)
    project_name = project.name if project else session_id

    logger.info("Published project '%s' (session %s) to %s (proxy: %s)", project_name, session_id, s3_url, proxy_url)

    return {"url": proxy_url, "project_name": project_name}
