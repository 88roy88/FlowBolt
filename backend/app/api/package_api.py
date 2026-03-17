"""Backend routes that proxy to the Package API (FLAPI).

These routes are what the frontend should call. They can later be pointed at
real FLAPI (cluster) or the local mock by switching configuration.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from app.config import settings
from app.integrations.package_api import PackageApiClient, PackageApiUpstreamError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/package", tags=["package"])


def _client() -> PackageApiClient:
    return PackageApiClient(base_url=settings.PACKAGE_API_BASE_URL)


@router.get("/v1/search/{query_or_id}")
async def package_search(query_or_id: str):
    """Proxy search-by-id or autocomplete to FLAPI.

    Mirrors: GET /package/v1/search/{query_or_id}
    """
    if not query_or_id.strip():
        raise HTTPException(status_code=422, detail="query_or_id is required")

    try:
        return await _client().search(query_or_id)
    except PackageApiUpstreamError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/v3/{package_id}")
async def run_package(
    package_id: str,
    allQueries: bool | None = Query(default=None),
    body: Any | None = Body(default=None),
):
    """Proxy 'run package' to FLAPI.

    Mirrors: POST /package/v3/{package_id}?allQueries=true
    """
    if not package_id.strip():
        raise HTTPException(status_code=422, detail="package_id is required")

    try:
        return await _client().run_package(package_id, all_queries=allQueries, body=body)
    except PackageApiUpstreamError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

