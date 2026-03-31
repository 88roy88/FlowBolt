"""Backend routes that proxy data-source search and execution.

These routes are what the frontend calls. The upstream implementation lives
in the integrations layer.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from flow44.api.deps import AuthDep
from flow44.integrations.flapi_api import FlapiUpstreamError, data_source_client

router = APIRouter(prefix="/api/data-source", tags=["data-source"])


@router.get("/search/{query_or_id}")
async def search_data_source(
    query_or_id: str,
    authorization: AuthDep,
) -> list[Any]:
    """Search for data sources by name or ID.

    Requires Authorization header from SSO.
    """
    try:
        return await data_source_client.search(query_or_id, authorization=authorization)
    except FlapiUpstreamError as err:
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err


@router.get("/{data_source_id}/run")
async def run_data_source(
    data_source_id: str,
    authorization: AuthDep,
) -> Any:
    """Execute a data source and return results.

    Requires Authorization header from SSO.
    """
    try:
        return await data_source_client.run_data_source(
            data_source_id,
            authorization=authorization,
        )
    except FlapiUpstreamError as err:
        status = 401 if err.status_code == 401 else 502
        raise HTTPException(status_code=status, detail=str(err)) from err
