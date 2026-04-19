from typing import Any

from fastapi import APIRouter, HTTPException, Body

from flow44.api.deps import AuthDep
from flow44.integrations.flapi_api import FlapiUpstreamError, data_source_client

router = APIRouter(prefix="/api/data-source", tags=["data-source"])


@router.get("/search/{query_or_id}")
async def search_data_source(
    authorization: AuthDep,
    query_or_id: str,
) -> list[Any]:
    try:
        return await data_source_client.search(query_or_id, authorization=authorization)
    except FlapiUpstreamError as err:
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err


@router.post("/{data_source_id}/run")
async def run_data_source(
    authorization: AuthDep,
    data_source_id: str,
    quick_params: dict[str, dict[str, Any]] | None = Body(None, examples=[{"personId": {"text": 2}}]),
) -> Any:
    try:
        return await data_source_client.run_data_source(
            data_source_id,
            authorization=authorization,
            quick_params=quick_params,
        )
    except FlapiUpstreamError as err:
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err
