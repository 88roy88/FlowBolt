from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from flow44.api.deps import UserDep, resolve_project_permissions
from flow44.auth.permissions import Permission, has_permission
from flow44.db.page_view import PageViewSource, increment_page_views
from flow44.db.project import get_project, get_project_by_handle
from flow44.services.logging import _project_id as _log_project_id
from flow44.services.logging import _project_name as _log_project_name
from flow44.services.logging import log_bi_event

router = APIRouter(prefix="/api/page-views", tags=["page_views"])


class PageViewRequest(BaseModel):
    source: PageViewSource
    # The project id for previews, the /shared/{handle} handle for production
    ref: str


@router.post("", status_code=204)
async def track_page_view(body: PageViewRequest, user_id: UserDep) -> None:
    """Count a page load of a generated app, sent by the app itself."""
    if body.source == PageViewSource.preview:
        project = await get_project(body.ref)
    else:
        project = await get_project_by_handle(body.ref)
        if project is not None and not project.published_at:
            project = None
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    await increment_page_views(project.id, body.source)

    can_write = has_permission(await resolve_project_permissions(project, user_id), Permission.write)

    _log_project_id.set(project.id)
    _log_project_name.set(project.name)
    log_bi_event("page_viewed", view_source=body.source.value, can_write=can_write)
