"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os

import litellm

from app.api import chat, export, files, models, preview, projects, terminal
from app.config import settings
from app.models.project import init_db
from app.sandbox.manager import sandbox_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: initialise DB on startup, clean up sandboxes on shutdown."""
    # Langfuse observability via OpenTelemetry (optional)
    # Settings are loaded from AIB_LANGFUSE_* env vars via pydantic-settings,
    # but LiteLLM reads bare LANGFUSE_* env vars at runtime — mirror them.
    # We use the "langfuse_otel" callback which sends traces over OTEL protocol,
    # avoiding direct langfuse SDK __init__() compatibility issues across versions.
    if settings.LANGFUSE_PUBLIC_KEY:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.LANGFUSE_PUBLIC_KEY)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.LANGFUSE_SECRET_KEY)
        os.environ.setdefault("LANGFUSE_OTEL_HOST", settings.LANGFUSE_HOST)
        litellm.callbacks = ["langfuse_otel"]
        logger.info("Langfuse OTEL tracing enabled (host=%s)", settings.LANGFUSE_HOST)
    else:
        logger.info("Langfuse tracing disabled (no LANGFUSE_PUBLIC_KEY set)")

    logger.info("Initialising database...")
    await init_db()
    logger.info("Database ready.")

    logger.info("Restoring existing sandbox workspaces...")
    await sandbox_manager.restore_existing_workspaces()
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

# WebSocket routers
app.include_router(chat.router)
app.include_router(terminal.router)
