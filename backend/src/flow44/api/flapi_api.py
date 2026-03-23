"""Backend routes that proxy to FLAPI (package search & execution).

These routes are what the frontend calls. They can later be pointed at
real FLAPI (cluster) or the local mock by switching configuration.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.security import APIKeyHeader

from flow44.integrations.data_source_cases import normalize_flapi_authorization, search_data_sources
from flow44.integrations.flapi_api import FlapiClient, FlapiUpstreamError

router = APIRouter(prefix="/api/data-source", tags=["data-source"])

# APIKeyHeader (not Header(alias=...)) so Swagger UI actually sends Authorization on Try it out.
_data_source_authorization = APIKeyHeader(name="Authorization", auto_error=False)


def _client(*, authorization: str | None) -> FlapiClient:
    from flow44.config import settings  # noqa: PLC0415

    return FlapiClient(base_url=settings.FLAPI_BASE_URL, authorization=authorization)


def _map_upstream_error(e: FlapiUpstreamError) -> HTTPException:
    if e.status_code == 401:
        return HTTPException(status_code=401, detail="FLAPI unauthorized")
    return HTTPException(status_code=502, detail=str(e))


async def _data_source_search(query_or_id: str, *, authorization: str | None) -> list[Any]:
    try:
        return await search_data_sources(query_or_id, authorization=authorization)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except FlapiUpstreamError as e:
        raise _map_upstream_error(e) from e


@router.get("/search/{query_or_id}")
async def data_source_search(
    query_or_id: str,
    authorization: Annotated[str | None, Depends(_data_source_authorization)] = None,
) -> list[Any]:
    """Proxy search-by-id or autocomplete to FLAPI."""
    return await _data_source_search(
        query_or_id,
        authorization=normalize_flapi_authorization(authorization),
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
        return await _client(authorization=authorization).run_data_source(
            data_source_id,
            all_queries=allQueries,
            body=body,
        )
    except FlapiUpstreamError as e:
        raise _map_upstream_error(e) from e


@router.post("/{data_source_id}/run")
async def run_data_source(
    data_source_id: str,
    allQueries: bool | None = Query(default=None),  # noqa: N803
    body: Any | None = Body(default=None),
    authorization: Annotated[str | None, Depends(_data_source_authorization)] = None,
) -> Any:
    """Proxy 'run package' to FLAPI."""
    return await _run_data_source(
        data_source_id,
        allQueries=allQueries,
        body=body,
        authorization=normalize_flapi_authorization(authorization),
    )


# get route as well
@router.get("/{data_source_id}/run")
async def run_data_source_get(
    data_source_id: str,
    allQueries: bool | None = Query(default=None),  # noqa: N803
    authorization: Annotated[str | None, Depends(_data_source_authorization)] = None,
) -> Any:
    """Proxy 'run package' to FLAPI."""
    return await _run_data_source(
        data_source_id,
        allQueries=allQueries,
        body=None,
        authorization=normalize_flapi_authorization(authorization),
    )
