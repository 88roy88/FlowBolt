"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os

import litellm
from langfuse import Langfuse

from app.api import chat, errors, export, files, models, package_api, preview, projects, publish, server_log, terminal
from app.config import settings
from app.models.project import init_db
from app.models.events import init_events_table
from app.sandbox.manager import sandbox_manager

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
    await init_events_table()
    logger.info("Database ready.")

    logger.info("Restoring existing sandbox workspaces...")
    from app.models.project import list_projects
    live_projects = await list_projects()
    live_session_ids = {p.session_id for p in live_projects}
    await sandbox_manager.restore_existing_workspaces(live_session_ids)
    logger.info("Sandbox restoration complete.")

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
app.include_router(package_api.router)

# WebSocket routers
app.include_router(chat.router)
app.include_router(terminal.router)
app.include_router(server_log.router)
app.include_router(errors.router)
