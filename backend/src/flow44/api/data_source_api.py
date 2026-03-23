"""Backend routes that proxy data-source search and execution.

These routes are what the frontend calls. The upstream implementation lives
in the integrations layer.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.security import APIKeyHeader

from flow44.integrations.data_source_cases import (
    DataSourceUpstreamError,
    normalize_data_source_authorization,
    search_data_sources,
)
from flow44.integrations.data_source_cases import (
    run_data_source as run_data_source_upstream,
)

router = APIRouter(prefix="/api/data-source", tags=["data-source"])

# APIKeyHeader (not Header(alias=...)) so Swagger UI sends Authorization in Try it out.
_data_source_authorization = APIKeyHeader(name="Authorization", auto_error=False)


def _map_upstream_error(err: DataSourceUpstreamError) -> HTTPException:
    if err.status_code == 401:
        return HTTPException(status_code=401, detail="Data source upstream unauthorized")
    return HTTPException(status_code=502, detail=str(err))


async def _data_source_search(query_or_id: str, *, authorization: str | None) -> list[Any]:
    try:
        return await search_data_sources(query_or_id, authorization=authorization)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    except DataSourceUpstreamError as err:
        raise _map_upstream_error(err) from err


@router.get("/search/{query_or_id}")
async def data_source_search(
    query_or_id: str,
    authorization: Annotated[str | None, Depends(_data_source_authorization)] = None,
) -> list[Any]:
    """Proxy search-by-id or autocomplete."""
    return await _data_source_search(
        query_or_id,
        authorization=normalize_data_source_authorization(authorization),
    )


async def _run_data_source(
    data_source_id: str,
    allQueries: bool | None,  # noqa: N803 — matches API query parameter name
    body: Any | None,
    *,
    authorization: str | None,
) -> Any:
    if not data_source_id.strip():
        raise HTTPException(status_code=422, detail="data_source_id is required")

    try:
        return await run_data_source_upstream(
            data_source_id,
            authorization=authorization,
            all_queries=allQueries,
            body=body,
        )
    except DataSourceUpstreamError as err:
        raise _map_upstream_error(err) from err


@router.post("/{data_source_id}/run")
async def run_data_source(
    data_source_id: str,
    allQueries: bool | None = Query(default=None),  # noqa: N803
    body: Any | None = Body(default=None),
    authorization: Annotated[str | None, Depends(_data_source_authorization)] = None,
) -> Any:
    """Proxy data-source execution to the upstream service."""
    return await _run_data_source(
        data_source_id,
        allQueries=allQueries,
        body=body,
        authorization=normalize_data_source_authorization(authorization),
    )


@router.get("/{data_source_id}/run")
async def run_data_source_get(
    data_source_id: str,
    allQueries: bool | None = Query(default=None),  # noqa: N803
    authorization: Annotated[str | None, Depends(_data_source_authorization)] = None,
) -> Any:
    """Proxy data-source execution to the upstream service."""
    return await _run_data_source(
        data_source_id,
        allQueries=allQueries,
        body=None,
        authorization=normalize_data_source_authorization(authorization),
    )
