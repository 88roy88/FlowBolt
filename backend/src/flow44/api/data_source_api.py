from fastapi import APIRouter, Body, HTTPException

from flow44.api.deps import AuthDep
from flow44.logic import data_source as ds_logic
from flow44.logic.models import (
    CanRunResponse,
    DataSource,
    DataSourceParams,
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
        can_run, minimal_params = await ds_logic.can_run_without_params(
            data_source_id,
            authorization=authorization,
        )
        return CanRunResponse(
            can_run=can_run,
            minimal_params=minimal_params.root if minimal_params else None,
        )
    except ds_logic.FlapiUpstreamError as err:
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err


@router.post("/{data_source_id}/run")
async def run_data_source(
    authorization: AuthDep,
    data_source_id: str,
    params: dict[str, str | int | bool] | None = Body(None, examples=[{"person_id": 2, "active": True}]),
) -> DataSourceResult:
    try:
        ds_params = DataSourceParams.model_validate(params) if params else None
        return await ds_logic.run_data_source(
            data_source_id,
            authorization=authorization,
            params=ds_params,
        )
    except ds_logic.FlapiUpstreamError as err:
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err
