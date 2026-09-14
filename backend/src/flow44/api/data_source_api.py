import time

from fastapi import APIRouter, Body, HTTPException
from pydantic import ValidationError

from flow44.api.deps import TokenDep as AuthDep
from flow44.integrations.flapi.models import CubeId, QuickParams, QuickParamValue
from flow44.logic import data_source as ds_logic
from flow44.logic.models import (
    CanRunResponse,
    DataSource,
    DataSourceParamsInfo,
    DataSourceResult,
    DataSourceUsage,
)
from flow44.services.logging import log_bi_event

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
    except ValidationError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err


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
    except ValidationError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err


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
    except ValidationError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err


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
    except ValidationError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err


@router.post("/{data_source_id}/run")
async def run_data_source(
    authorization: AuthDep,
    data_source_id: str,
    params: dict[CubeId, dict[str, QuickParamValue]] | None = Body(
        None,
        examples=[{"cube-1": {"person_id": 2, "active": True, "tag_ids": [10, 11]}}],
    ),
) -> DataSourceResult:
    start_time = time.monotonic()
    try:
        quick_params = QuickParams(root=params) if params else None
        result = await ds_logic.run_data_source(
            data_source_id,
            authorization=authorization,
            params=quick_params,
            execute_continued_process=True,
        )
        duration_ms = int((time.monotonic() - start_time) * 1000)
        log_bi_event(
            "flapi_call_made",
            {
                "data_source_id": data_source_id,
                "endpoint": "run",
                "duration_ms": duration_ms,
                "status_code": 200,
                "is_error": False,
            },
        )
        return result
    except ds_logic.FlapiUpstreamError as err:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        log_bi_event(
            "flapi_call_made",
            {
                "data_source_id": data_source_id,
                "endpoint": "run",
                "duration_ms": duration_ms,
                "status_code": err.status_code,
                "is_error": True,
                "error_message": str(err),
            },
        )
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err
    except ValidationError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err
