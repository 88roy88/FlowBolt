from fastapi import APIRouter
from pydantic import BaseModel

from flow44.api.deps import Permission, ProjectDep, SandboxDep, TokenDep, require_permission
from flow44.logic import project_data_sources as ds_logic

router = APIRouter(prefix="/api/projects/{project_id}/data-sources", tags=["project-data-sources"])


class ProjectDataSourceItem(BaseModel):
    data_source_id: str
    name: str
    module_path: str
    package_updated_date: str | None
    params: list[ds_logic.ParamLabel]


@router.get("", dependencies=[require_permission(Permission.read)])
async def list_data_sources(project: ProjectDep, sandbox: SandboxDep) -> list[ProjectDataSourceItem]:
    return [
        ProjectDataSourceItem(
            data_source_id=ds.data_source_id,
            name=ds.data_source_name,
            module_path=ds_logic.module_path(ds),
            package_updated_date=await ds_logic.read_package_updated_date(sandbox, ds) or None,
            params=ds_logic.param_labels(ds),
        )
        for ds in await ds_logic.list_active(project.id, sandbox)
    ]


# Apart from the list, so a slow or unavailable FLAPI never delays or breaks it.
@router.get("/updates", dependencies=[require_permission(Permission.read)])
async def list_updates(
    project: ProjectDep, sandbox: SandboxDep, authorization: TokenDep = None
) -> list[ds_logic.PackageUpdate]:
    sources = await ds_logic.list_active(project.id, sandbox)
    return await ds_logic.find_updates(sandbox, sources, authorization)
