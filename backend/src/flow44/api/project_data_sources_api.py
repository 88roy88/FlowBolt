from functools import partial

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from flow44.ai.agents.routing import is_new_project
from flow44.api.deps import Permission, ProjectDep, SandboxDep, TokenDep, require_permission
from flow44.db.project_data_source import DataSourceContext
from flow44.logic import project_data_sources as ds_logic
from flow44.sandbox.main import PnpmSandbox
from flow44.services.logging import log_bi_event
from flow44.services.versioning import service as versioning

router = APIRouter(prefix="/api/projects/{project_id}/data-sources", tags=["project-data-sources"])


class ProjectDataSourceItem(BaseModel):
    data_source_id: str
    name: str
    module_path: str
    package_updated_date: str | None
    params: list[ds_logic.ParamLabel]


async def _get_active(project_id: str, sandbox: PnpmSandbox, data_source_id: str) -> DataSourceContext:
    for ds in await ds_logic.list_active(project_id, sandbox):
        if ds.data_source_id == data_source_id:
            return ds
    raise HTTPException(status_code=404, detail="Data source not found")


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


@router.get("/{data_source_id}/usages", dependencies=[require_permission(Permission.write)])
async def get_usages(project: ProjectDep, sandbox: SandboxDep, data_source_id: str) -> list[ds_logic.Usage]:
    ds = await _get_active(project.id, sandbox, data_source_id)
    return await ds_logic.find_usages(sandbox, ds)


@router.delete("/{data_source_id}", status_code=204, dependencies=[require_permission(Permission.write)])
async def delete_data_source(project: ProjectDep, sandbox: SandboxDep, data_source_id: str) -> None:
    # Before the first build, a paused interview or plan holds the data sources and would write them back.
    if await is_new_project(project.id):
        raise HTTPException(
            status_code=409, detail={"code": "not_built", "message": "Finish building the app before removing"}
        )
    ds = await _get_active(project.id, sandbox, data_source_id)
    name = ds.data_source_name
    try:
        await versioning.commit_user_change(
            project.id,
            message=f"Remove data source {name}",
            note=f'[I removed the data source "{name}". Don\'t use it or recreate its files.]',
            change=partial(ds_logic.delete_module, sandbox, ds),
        )
    except ds_logic.DataSourceInUse as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "in_use", "message": str(exc), "usages": [u.model_dump() for u in exc.usages]},
        ) from None
    except versioning.WorkspaceLocked as exc:
        raise HTTPException(status_code=409, detail=exc.payload) from None
    log_bi_event("data_source_removed", data_source_type=ds.type, data_source_id=data_source_id)
