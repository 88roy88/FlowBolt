import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

from fastapi import APIRouter
from pydantic import BaseModel

from flow44.api.admin import AdminDep
from flow44.config import settings
from flow44.db.project import Project, list_all_projects
from flow44.services.maintenance_utils import fix_file_permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/maintenance", tags=["admin", "maintenance"])


class ProjectMaintenanceResult(BaseModel):
    project_id: str
    project_name: str
    success: bool
    detail: str


async def _run_over_projects(op: Callable[[Project], Awaitable[str]]) -> list[ProjectMaintenanceResult]:
    """Run `op` against every project, capturing a per-project success/failure result."""
    projects = await list_all_projects()
    results: list[ProjectMaintenanceResult] = []
    for project in projects:
        try:
            detail = await op(project)
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


@router.post("/fix-file-permissions")
async def fix_workspace_file_permissions(_admin: AdminDep) -> list[ProjectMaintenanceResult]:
    """Make every non-world-writable file (e.g. -rw-r--r--) in each project's workspace world-writable.

    New files created by this process are already world-writable thanks to changing os.umask to 0.
    """

    async def op(project: Project) -> str:
        workspace_dir = os.path.join(settings.WORKSPACE_BASE_DIR, project.id)
        return await asyncio.to_thread(fix_file_permissions, workspace_dir)

    return await _run_over_projects(op)
