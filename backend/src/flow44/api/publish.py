import asyncio
import logging
import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from flow44.config import settings
from flow44.db.project import is_handle_taken, update_project_published_url
from flow44.integrations.s3 import deploy_single_html
from flow44.sandbox.operations import BuildError, build_single_html

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export/{project_id}", tags=["publish"])

# Authoritative slug rule — mirrored by SLUG_RE in frontend stores/publish.ts.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")


class PublishRequest(BaseModel):
    slug: str | None = None


async def _slug_status(slug: str, project_id: str) -> Literal["available", "invalid", "taken"]:
    """Single source of truth for whether a slug may be used by this project."""
    if not _SLUG_RE.match(slug):
        return "invalid"
    if await is_handle_taken(slug, exclude_project_id=project_id):
        return "taken"
    return "available"


@router.get("/slug/check")
async def check_slug(project_id: str, slug: str = Query(...)) -> dict[str, bool]:
    """Return whether a slug is available for this project."""
    return {"available": await _slug_status(slug, project_id) == "available"}


async def _validate_slug(slug: str, project_id: str) -> None:
    status = await _slug_status(slug, project_id)
    if status == "invalid":
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid slug. Use 3–50 lowercase letters, numbers, and hyphens"
                " (must start and end with a letter or digit)."
            ),
        )
    if status == "taken":
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
        await loop.run_in_executor(None, deploy_single_html, html_content, project_id)
    except Exception as exc:
        logger.exception("S3 deployment failed for project %s", project_id)
        raise HTTPException(status_code=502, detail=f"S3 deployment failed: {exc}") from exc

    handle = slug or project_id
    try:
        published_at = await update_project_published_url(project_id, handle)
    except IntegrityError as exc:
        logger.warning("Handle collision for project %s with handle %s: %s", project_id, handle, exc)
        raise HTTPException(
            status_code=409, detail=f"The handle '{handle}' was just claimed by another project."
        ) from exc

    if published_at is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    public_path = f"/shared/{handle}"
    logger.info("Published project %s (handle: %s, public: %s)", project_id, handle, public_path)

    return {"url": public_path, "handle": handle, "published_at": published_at}
