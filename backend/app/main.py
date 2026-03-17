"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os

import litellm

from app.api import chat, errors, export, files, models, preview, projects, server_log, terminal
from app.config import settings
from app.models.project import init_db
from app.sandbox.manager import sandbox_manager
from app.sandbox.pty import cleanup_all_ptys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: initialise DB on startup, clean up sandboxes on shutdown."""
    # Langfuse observability (optional) — using langfuse 2.59.7 (compatible with litellm)
    if settings.LANGFUSE_PUBLIC_KEY:
        # TODO: remove from here.
        os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-5b72f594-fa75-4a2d-847f-d037a6cf34f8"
        os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-4ebc8ff8-da65-484b-8747-6af8ab49b600"
        os.environ["LANGFUSE_HOST"] = "https://cloud.langfuse.com"
        # set langfuse as a callback, litellm will send the data to langfuse
        litellm.success_callback = ["langfuse"]
        litellm.failure_callback = ["langfuse"]
        logger.info("Langfuse tracing enabled (host=%s)", settings.LANGFUSE_HOST)
    else:
        logger.info("Langfuse tracing disabled (no LANGFUSE_PUBLIC_KEY set)")

    logger.info("Initialising database...")
    await init_db()
    logger.info("Database ready.")

    logger.info("Restoring existing sandbox workspaces...")
    await sandbox_manager.restore_existing_workspaces()
    logger.info("Sandbox restoration complete.")

    yield
    logger.info("Shutting down — killing PTY processes...")
    cleanup_all_ptys()
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

# WebSocket routers
app.include_router(chat.router)
app.include_router(terminal.router)
app.include_router(server_log.router)
app.include_router(errors.router)


if __name__ == "__main__":
    import uvicorn
    print(f"Starting backend server...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["data/**", "*.db"],
        reload_delay=5.0,  # wait 5s after file change before reloading
    )