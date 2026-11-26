import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import AfterValidator, BaseModel, StringConstraints
from sqlalchemy.exc import IntegrityError

from flow44.api.deps import Permission, ProjectDep, require_permission
from flow44.config import settings
from flow44.db.project import PublishDetails
from flow44.logic.publish import SlugStatus, publish_project, resolve_slug_status
from flow44.logic.publish_form import get_publish_form_config
from flow44.sandbox.operations import BuildError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export/{project_id}", tags=["publish"])


class PublishRequest(BaseModel):
    slug: str | None = None
    app_type: str
    app_description: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, max_length=settings.APP_DESCRIPTION_MAX_CHARS),
            AfterValidator(lambda text: text or None),
        ]
        | None
    ) = None
    publish_reason: str | None = None


def _validate_details(body: PublishRequest) -> PublishDetails:
    config = get_publish_form_config()
    if body.app_type not in {app_type.id for app_type in config.app_types}:
        raise HTTPException(status_code=400, detail=f"Unknown app type '{body.app_type}'.")
    if body.publish_reason is not None and body.publish_reason not in config.publish_reasons:
        raise HTTPException(status_code=400, detail=f"Unknown publish reason '{body.publish_reason}'.")
    return PublishDetails(
        app_type=body.app_type, app_description=body.app_description, publish_reason=body.publish_reason
    )


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
    body: PublishRequest,
    _perms: set[Permission] = require_permission(Permission.publish),
) -> dict[str, str]:
    details = _validate_details(body)
    slug = body.slug or None
    if slug:
        await _validate_slug(slug, project.id)

    try:
        handle = await publish_project(project.id, slug, details)
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
