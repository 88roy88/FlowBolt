import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import litellm
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from flow44.api import (
    admin,
    chat,
    data_source_api,
    errors,
    export,
    files,
    iaagent,
    members,
    models,
    preview,
    projects,
    publish,
    server_log,
    shared,
    terminal,
)
from flow44.api.deps import validate_token, validate_ws_token
from flow44.config import settings
from flow44.db.database import init_db
from flow44.db.project import list_all_projects
from flow44.integrations.s3 import setup_bucket
from flow44.sandbox.idle_reaper import idle_reaper
from flow44.sandbox.manager import sandbox_manager
from flow44.services.heartbeat_reaper import heartbeat_reaper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        # Credentials already in os.environ via LangfuseSettings.model_post_init
        litellm.success_callback = ["langfuse"]
        litellm.failure_callback = ["langfuse"]
        logger.info("Langfuse tracing enabled")
    else:
        logger.info("Langfuse tracing not enabled (missing keys)")

    logger.info("Initialising database...")
    await init_db()
    logger.info("Database ready.")

    logger.info("Restoring existing sandbox workspaces...")

    live_projects = await list_all_projects()

    live_project_ids = {p.id for p in live_projects}
    await sandbox_manager.reconcile_workspaces(live_project_ids)
    logger.info("Sandbox restoration complete.")

    idle_reaper.start()
    logger.info("Idle reaper started (TTL=%ds).", settings.SANDBOX_IDLE_TTL_SECONDS)

    heartbeat_reaper.start()
    logger.info("Heartbeat reaper started (stale=%ds).", settings.AGENT_RUN_STALE_TIMEOUT)

    if settings.S3_BUCKET_NAME:
        logger.info("Setting up S3 bucket: %s", settings.S3_BUCKET_NAME)
        try:
            # TODO: if we keep this here, we should add check_bucket_exists and only call create if not.
            setup_bucket(settings.S3_BUCKET_NAME)
            logger.info("S3 bucket setup complete.")
        except Exception as exc:
            logger.warning("S3 bucket setup issue (may already exist or be misconfigured): %s", exc)

    yield
    logger.info("Shutting down — stopping reapers and destroying all sandboxes...")
    await idle_reaper.stop()
    await heartbeat_reaper.stop()
    await sandbox_manager.suspend_all()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="AI Web App Builder",
    version="0.1.0",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for Docker/K8s."""
    return {"status": "ok", "version": "0.1.0"}


# CORS — allow all origins in development
# TODO: limit CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authenticated HTTP routes
auth_routes = APIRouter(dependencies=[Depends(validate_token)])
auth_routes.include_router(projects.router)
auth_routes.include_router(files.router)
auth_routes.include_router(preview.router)
auth_routes.include_router(export.router)
auth_routes.include_router(publish.router)
auth_routes.include_router(data_source_api.router)
auth_routes.include_router(chat.http_router)
auth_routes.include_router(iaagent.router)
auth_routes.include_router(members.router)
auth_routes.include_router(admin.router)
app.include_router(auth_routes)

# Public HTTP routes
public_routes = APIRouter()
public_routes.include_router(models.router)
public_routes.include_router(shared.router)
app.include_router(public_routes)

# Authenticated WS routes
ws_auth_routes = APIRouter(dependencies=[Depends(validate_ws_token)])
ws_auth_routes.include_router(chat.ws_router)
ws_auth_routes.include_router(terminal.router)
ws_auth_routes.include_router(server_log.router)
ws_auth_routes.include_router(errors.router)
app.include_router(ws_auth_routes)
