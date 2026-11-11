import logging

from fastapi import Request

from flow44.db.page_view import PageViewSource, increment_page_views
from flow44.db.project import Project
from flow44.services.logging import _project_id as _log_project_id
from flow44.services.logging import _project_name as _log_project_name
from flow44.services.logging import log_bi_event

logger = logging.getLogger(__name__)


def is_page_load(request: Request) -> bool:
    return request.method == "GET" and request.headers.get("sec-fetch-mode") == "navigate"


def is_iframe(request: Request) -> bool:
    return request.headers.get("sec-fetch-dest") == "iframe"


async def record_page_view(project: Project, source: PageViewSource) -> None:
    try:
        await increment_page_views(project.id, source)
        _log_project_id.set(project.id)
        _log_project_name.set(project.name)
        log_bi_event("page_viewed", view_source=source.value)
    except Exception:
        logger.exception("Failed to record %s page view for project %s", source.value, project.id)
