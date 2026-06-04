from typing import Any

from fastapi import APIRouter, HTTPException

from flow44.api.deps import TokenDep
from flow44.integrations.flapi_api import FlapiUpstreamError, data_source_client

router = APIRouter(prefix="/api/data-source", tags=["data-source"])


@router.get("/search/{query_or_id}")
async def search_data_source(query_or_id: str, authorization: TokenDep) -> list[Any]:
    try:
        return await data_source_client.search(query_or_id, authorization=authorization)
    except FlapiUpstreamError as err:
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err


@router.get("/{data_source_id}/run")
async def run_data_source(data_source_id: str, authorization: TokenDep) -> Any:
    try:
        return await data_source_client.run_data_source(data_source_id, authorization=authorization)
    except FlapiUpstreamError as err:
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err
