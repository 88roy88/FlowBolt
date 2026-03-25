"""Backend routes that proxy data-source search and execution.

These routes are what the frontend calls. The upstream implementation lives
in the integrations layer.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import APIKeyHeader

from flow44.integrations.flapi_api import FlapiUpstreamError, data_source_client

router = APIRouter(prefix="/api/data-source", tags=["data-source"])

_data_source_authorization = APIKeyHeader(name="Authorization", auto_error=False)


@router.get("/search/{query_or_id}")
async def search_data_source(
    query_or_id: str,
    authorization: Annotated[str | None, Depends(_data_source_authorization)] = None,
) -> list[Any]:
    try:
        return await data_source_client.search(query_or_id, authorization=authorization)
    except FlapiUpstreamError as err:
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err


@router.get("/{data_source_id}/run")
async def run_data_source(
    data_source_id: str,
    authorization: Annotated[str | None, Depends(_data_source_authorization)] = None,
) -> Any:
    try:
        return await data_source_client.run_data_source(
            data_source_id,
            authorization=authorization,
        )
    except FlapiUpstreamError as err:
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err
