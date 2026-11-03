"""Page view counting for generated apps, decided from the page request the backend serves.

Browsers mark a page load with ``Sec-Fetch-Mode: navigate``, and a page loaded inside an
iframe with ``Sec-Fetch-Dest: iframe``. That tells a preview opened in its own tab apart from
the builder's preview iframe, which reloads on every edit and is not counted.
"""

import logging

from fastapi import Request

from flow44.api.deps import decode_token, get_authorization_header, resolve_project_permissions
from flow44.auth.permissions import Permission, has_permission
from flow44.config import settings
from flow44.db.page_view import PageViewSource, increment_page_views
from flow44.db.project import Project
from flow44.services.logging import _project_id as _log_project_id
from flow44.services.logging import _project_name as _log_project_name
from flow44.services.logging import log_bi_event

logger = logging.getLogger(__name__)


def is_page_load(request: Request, content_type: str | None) -> bool:
    """A browser navigation to an HTML page (a tab, a link, an iframe), not a fetch or an asset."""
    return (
        request.method == "GET"
        and request.headers.get("sec-fetch-mode") == "navigate"
        and (content_type or "").startswith("text/html")
    )


def is_iframe(request: Request) -> bool:
    return request.headers.get("sec-fetch-dest") == "iframe"


async def _viewer_can_write(project: Project, request: Request) -> bool:
    """Whether the signed-in viewer, if any, has write access. Published apps are served without auth."""
    token = get_authorization_header(
        request.headers.get("authorization"), request.cookies.get(settings.AUTH_COOKIE_NAME)
    )
    payload = decode_token(token) if token else None
    if payload is None or not payload.unique_id:
        return False
    return has_permission(await resolve_project_permissions(project, payload.unique_id), Permission.write)


async def record_page_view(
    project: Project, source: PageViewSource, request: Request, can_write: bool | None = None
) -> None:
    """Count one page view. Never raises: counting must not affect serving the app."""
    try:
        await increment_page_views(project.id, source)
        if can_write is None:
            can_write = await _viewer_can_write(project, request)
        _log_project_id.set(project.id)
        _log_project_name.set(project.name)
        log_bi_event("page_viewed", view_source=source.value, can_write=can_write)
    except Exception:
        logger.exception("Failed to record %s page view for project %s", source.value, project.id)
