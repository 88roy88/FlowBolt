import logging
from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from flow44.db.project import Project, list_all_projects

logger = logging.getLogger(__name__)


class ProjectMaintenanceResult(BaseModel):
    project_id: str
    project_name: str
    success: bool
    detail: str


async def run_over_projects(operation: Callable[[Project], Awaitable[str]]) -> list[ProjectMaintenanceResult]:
    projects = await list_all_projects()
    results: list[ProjectMaintenanceResult] = []
    for project in projects:
        try:
            detail = await operation(project)
            result = ProjectMaintenanceResult(
                project_id=project.id, project_name=project.name, success=True, detail=detail
            )
        except Exception as exc:
            logger.exception("Maintenance op failed for project %s", project.id)
            result = ProjectMaintenanceResult(
                project_id=project.id, project_name=project.name, success=False, detail=str(exc)
            )
        results.append(result)
        logger.debug(
            "[%s] project %s (%s): %s",
            "ok" if result.success else "FAILED",
            result.project_id,
            result.project_name,
            result.detail,
        )
    return results
