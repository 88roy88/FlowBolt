"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import litellm
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langfuse import Langfuse

from flow44.api import (
    chat,
    data_source_api,
    errors,
    export,
    files,
    models,
    preview,
    projects,
    publish,
    server_log,
    terminal,
)
from flow44.config import settings
from flow44.db.database import init_db
from flow44.integrations.s3 import setup_bucket
from flow44.sandbox.manager import sandbox_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: initialise DB on startup, clean up sandboxes on shutdown."""
    # Langfuse observability (optional) — using langfuse 2.59.7 (compatible with litellm)
    if settings.LANGFUSE_PUBLIC_KEY:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
        os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_HOST

        # Initialize Langfuse client for decorator usage
        Langfuse()

        # Set langfuse as a callback, litellm will send the data to langfuse
        litellm.success_callback = ["langfuse"]
        litellm.failure_callback = ["langfuse"]
        logger.info("Langfuse tracing enabled (host=%s)", settings.LANGFUSE_HOST)
    else:
        logger.info("Langfuse tracing disabled (no LANGFUSE_PUBLIC_KEY set)")

    logger.info("Initialising database...")
    await init_db()
    logger.info("Database ready.")

    logger.info("Restoring existing sandbox workspaces...")
    from flow44.db.project import list_projects  # noqa: PLC0415

    live_projects = await list_projects()

    live_project_ids = {p.id for p in live_projects}
    await sandbox_manager.restore_existing_workspaces(live_project_ids)
    logger.info("Sandbox restoration complete.")

    if settings.S3_BUCKET_NAME:
        logger.info("Setting up S3 bucket: %s", settings.S3_BUCKET_NAME)
        try:
            setup_bucket(settings.S3_BUCKET_NAME)
            logger.info("S3 bucket setup complete.")
        except Exception as exc:
            logger.warning("S3 bucket setup issue (may already exist or be misconfigured): %s", exc)

    yield
    logger.info("Shutting down — destroying all sandboxes...")
    await sandbox_manager.destroy_all()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="AI Web App Builder",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow all origins in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routers
app.include_router(projects.router)
app.include_router(files.router)
app.include_router(preview.router)
app.include_router(models.router)
app.include_router(export.router)
app.include_router(publish.router)
app.include_router(data_source_api.router)

# WebSocket routers
app.include_router(chat.router)
app.include_router(terminal.router)
app.include_router(server_log.router)
app.include_router(errors.router)
