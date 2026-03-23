"""Backend routes that proxy to the Package API (FLAPI).

These routes are what the frontend should call. They can later be pointed at
real FLAPI (cluster) or the local mock by switching configuration.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.security import APIKeyHeader

from flow44.config import settings
from flow44.integrations.package_api import PackageApiClient, PackageApiUpstreamError
from flow44.integrations.package_cases import normalize_package_authorization, search_packages

router = APIRouter(prefix="/api/package", tags=["package"])

# APIKeyHeader (not Header(alias=...)) so Swagger UI actually sends Authorization on Try it out.
_package_authorization = APIKeyHeader(name="Authorization", auto_error=False)


def _client(*, authorization: str | None) -> PackageApiClient:
    return PackageApiClient(base_url=settings.PACKAGE_API_BASE_URL, authorization=authorization)


def _map_upstream_error(e: PackageApiUpstreamError) -> HTTPException:
    if e.status_code == 401:
        return HTTPException(status_code=401, detail="Package API unauthorized")
    return HTTPException(status_code=502, detail=str(e))


async def _package_search(query_or_id: str, *, authorization: str | None) -> list[Any]:
    try:
        return await search_packages(query_or_id, authorization=authorization)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except PackageApiUpstreamError as e:
        raise _map_upstream_error(e) from e


@router.get("/search/{query_or_id}")
async def package_search(
    query_or_id: str,
    authorization: Annotated[str | None, Depends(_package_authorization)] = None,
) -> list[Any]:
    """Proxy search-by-id or autocomplete to FLAPI."""
    return await _package_search(
        query_or_id,
        authorization=normalize_package_authorization(authorization),
    )


async def _run_package(
    package_id: str,
    allQueries: bool | None,  # noqa: N803 — matches API query parameter name
    body: Any | None,
    *,
    authorization: str | None,
) -> Any:
    if not package_id.strip():
        raise HTTPException(status_code=422, detail="package_id is required")

    try:
        return await _client(authorization=authorization).run_package(package_id, all_queries=allQueries, body=body)
    except PackageApiUpstreamError as e:
        raise _map_upstream_error(e) from e


@router.post("/{package_id}/run")
async def run_package(
    package_id: str,
    allQueries: bool | None = Query(default=None),  # noqa: N803
    body: Any | None = Body(default=None),
    authorization: Annotated[str | None, Depends(_package_authorization)] = None,
) -> Any:
    """Proxy 'run package' to FLAPI."""
    return await _run_package(
        package_id,
        allQueries=allQueries,
        body=body,
        authorization=normalize_package_authorization(authorization),
    )


# get route as well
@router.get("/{package_id}/run")
async def run_package_get(
    package_id: str,
    allQueries: bool | None = Query(default=None),  # noqa: N803
    authorization: Annotated[str | None, Depends(_package_authorization)] = None,
) -> Any:
    """Proxy 'run package' to FLAPI."""
    return await _run_package(
        package_id,
        allQueries=allQueries,
        body=None,
        authorization=normalize_package_authorization(authorization),
    )
