"""Backend routes that proxy to FLAPI (package search & execution).

These routes are what the frontend calls. They can later be pointed at
real FLAPI (cluster) or the local mock by switching configuration.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from flow44.config import settings
from flow44.integrations.flapi_api import FlapiClient, FlapiUpstreamError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data-source", tags=["data-source"])


def _client() -> FlapiClient:
    return FlapiClient(base_url=settings.FLAPI_BASE_URL)


async def _package_search(query_or_id: str) -> list[Any]:
    if not query_or_id.strip():
        raise HTTPException(status_code=422, detail="query_or_id is required")

    try:
        return await _client().search(query_or_id)
    except FlapiUpstreamError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/search/{query_or_id}")
async def package_search(query_or_id: str) -> list[Any]:
    """Proxy search-by-id or autocomplete to FLAPI."""
    return await _package_search(query_or_id)


async def _run_package(
    package_id: str,
    allQueries: bool | None,  # noqa: N803 — matches API query parameter name
    body: Any | None,
) -> Any:
    if not package_id.strip():
        raise HTTPException(status_code=422, detail="package_id is required")

    try:
        return await _client().run_package(package_id, all_queries=allQueries, body=body)
    except FlapiUpstreamError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/{package_id}/run")
async def run_package(
    package_id: str,
    allQueries: bool | None = Query(default=None),  # noqa: N803
    body: Any | None = Body(default=None),
) -> Any:
    """Proxy 'run package' to FLAPI."""
    return await _run_package(package_id, allQueries=allQueries, body=body)


# get route as well
@router.get("/{package_id}/run")
async def run_package_get(
    package_id: str,
    allQueries: bool | None = Query(default=None),  # noqa: N803
) -> Any:
    """Proxy 'run package' to FLAPI."""
    return await _run_package(package_id, allQueries=allQueries, body=None)
