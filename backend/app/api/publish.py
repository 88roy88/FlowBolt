"""REST endpoint for publishing a project to S3."""

from __future__ import annotations

import io
import logging
import os
import zipfile

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.integrations.s3 import deploy_react_app, setup_bucket, BUCKET_NAME
from app.models.project import get_project_by_session
from app.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export/{session_id}", tags=["publish"])


@router.post("/publish")
async def publish_to_s3(session_id: str):
    """Build the project and deploy to S3, returning the public URL."""
    sandbox = sandbox_manager.get_sandbox(session_id)
    if sandbox is None:
        raise HTTPException(status_code=404, detail=f"No sandbox found for session {session_id}")

    workspace_dir = sandbox.workspace_dir

    # Ensure the bucket exists with public-read policy
    try:
        setup_bucket(BUCKET_NAME)
    except Exception as exc:
        logger.warning("Bucket setup issue (may already exist): %s", exc)

    # Ensure the built React app knows the absolute URL for the API
    # so it does not send requests to relative paths on the static host.
    api_base = settings.EXPORT_API_BASE_URL or "http://localhost:8000"
    await sandbox.write_file(".env.production.local", f"VITE_API_BASE={api_base}\n")

    # Build the project
    build_output_lines: list[str] = []
    async for line in sandbox.exec("npx vite build --base ./ 2>&1"):
        build_output_lines.append(line)
    build_output = "".join(build_output_lines)

    dist_dir = os.path.join(workspace_dir, "dist")
    if not os.path.isdir(dist_dir):
        raise HTTPException(
            status_code=500,
            detail=f"Build failed or dist/ directory not found.\n\n{build_output}",
        )

    # Create an in-memory ZIP of the dist/ folder
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(dist_dir):
            for filename in files:
                abs_path = os.path.join(root, filename)
                arc_name = os.path.join("dist", os.path.relpath(abs_path, dist_dir))
                try:
                    zf.write(abs_path, arc_name)
                except (PermissionError, OSError) as exc:
                    logger.warning("Skipping file %s: %s", arc_name, exc)

    zip_buffer.seek(0)

    # Deploy to S3
    try:
        url = deploy_react_app(zip_buffer, session_id)
    except Exception as exc:
        logger.exception("S3 deployment failed for session %s", session_id)
        raise HTTPException(status_code=502, detail=f"S3 deployment failed: {exc}")

    project = await get_project_by_session(session_id)
    project_name = project.name if project else session_id

    logger.info("Published project '%s' (session %s) to %s", project_name, session_id, url)

    return {"url": url, "project_name": project_name}
