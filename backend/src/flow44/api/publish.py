import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from flow44.api.deps import Permission, ProjectDep, require_permission
from flow44.logic.publish import SlugStatus, publish_project, resolve_slug_status
from flow44.sandbox.operations import BuildError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export/{project_id}", tags=["publish"])


class PublishRequest(BaseModel):
    slug: str | None = None


@router.get("/slug/check")
async def check_slug(project_id: str, slug: str = Query(...)) -> dict[str, bool]:
    return {"available": await resolve_slug_status(slug, project_id) == SlugStatus.available}


async def _validate_slug(slug: str, project_id: str) -> None:
    status = await resolve_slug_status(slug, project_id)
    if status == SlugStatus.invalid:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid slug. Use 3–50 lowercase letters, numbers, and hyphens"
                " (must start and end with a letter or digit)."
            ),
        )
    if status == SlugStatus.taken:
        raise HTTPException(status_code=409, detail=f"The slug '{slug}' is already taken.")


@router.post("/publish")
async def publish_to_s3(
    project: ProjectDep,
    body: PublishRequest = PublishRequest(),
    _perms: set[Permission] = require_permission(Permission.publish),
) -> dict[str, str]:
    slug = body.slug or None
    if slug:
        await _validate_slug(slug, project.id)

    try:
        handle = await publish_project(project.id, slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BuildError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except IntegrityError as exc:
        logger.warning("Handle collision for project %s: %s", project.id, exc)
        raise HTTPException(status_code=409, detail=f"The handle '{slug or project.id}' was just claimed.") from exc
    except Exception as exc:
        logger.exception("Publish failed for project %s", project.id)
        raise HTTPException(status_code=502, detail=f"Publish failed: {exc}") from exc

    logger.info("Published project %s (handle: %s)", project.id, handle)
    return {"url": f"/shared/{handle}", "handle": handle}
