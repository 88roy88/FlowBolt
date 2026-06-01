from fastapi import APIRouter, Body, HTTPException

from flow44.api.deps import AuthDep
from flow44.logic import data_source as ds_logic
from flow44.integrations.flapi.models import CubeId, QuickParamValue, QuickParams
from flow44.logic.models import (
    CanRunResponse,
    DataSource,
    DataSourceParamsInfo,
    DataSourceResult,
    DataSourceUsage,
)

router = APIRouter(prefix="/api/data-source", tags=["data-source"])


@router.get("/search/{query_or_id}")
async def search_data_source(
    authorization: AuthDep,
    query_or_id: str,
) -> list[DataSource]:
    try:
        return await ds_logic.search_data_sources(query_or_id, authorization=authorization)
    except ds_logic.FlapiUpstreamError as err:
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err


@router.get("/{data_source_id}/params")
async def get_params_info(
    authorization: AuthDep,
    data_source_id: str,
) -> DataSourceParamsInfo:
    try:
        return await ds_logic.get_params_info(data_source_id, authorization=authorization)
    except ds_logic.FlapiUpstreamError as err:
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err


@router.get("/{data_source_id}/usage")
async def get_usage(
    authorization: AuthDep,
    data_source_id: str,
) -> DataSourceUsage:
    try:
        return await ds_logic.get_usage(
            data_source_id,
            authorization=authorization,
        )
    except ds_logic.FlapiUpstreamError as err:
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err


@router.get("/{data_source_id}/can-run")
async def can_run_without_params(
    authorization: AuthDep,
    data_source_id: str,
) -> CanRunResponse:
    try:
        can_run, _minimal = await ds_logic.can_run_without_params(
            data_source_id,
            authorization=authorization,
        )
        return CanRunResponse(can_run=can_run)
    except ds_logic.FlapiUpstreamError as err:
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err


@router.post("/{data_source_id}/run")
async def run_data_source(
    authorization: AuthDep,
    data_source_id: str,
    params: dict[CubeId, dict[str, QuickParamValue]] | None = Body(
        None,
        examples=[{"cube-1": {"person_id": 2, "active": True, "tag_ids": [10, 11]}}],
    ),
) -> DataSourceResult:
    try:
        quick_params = QuickParams(root=params) if params else None
        return await ds_logic.run_data_source(
            data_source_id,
            authorization=authorization,
            params=quick_params,
        )
    except ds_logic.FlapiUpstreamError as err:
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err
