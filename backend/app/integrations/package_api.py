"""Package API (FLAPI) client used by backend routes.

This module intentionally keeps all upstream (FLAPI) HTTP concerns isolated:
timeouts, error mapping, and URL construction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import quote
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PackageApiUpstreamError(RuntimeError):
    """Raised when the upstream Package API returns an error or is unreachable."""


@dataclass(frozen=True, slots=True)
class PackageApiClient:
    base_url: str
    timeout_s: float = 20.0

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    async def search(self, query_or_id: str) -> list[Any]:
        safe = quote(str(query_or_id), safe="")
        url = self._url(f"/package/v1/search/{safe}")
        return await self._get_json(url)

    async def run_package(self, package_id: str, *, all_queries: bool | None, body: Any | None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if all_queries is not None:
            # Upstream uses allQueries=true/false
            params["allQueries"] = "true" if all_queries else "false"
        safe = quote(str(package_id), safe="")
        url = self._url(f"/package/v3/{safe}")
        return await self._post_json(url, params=params, json=body)

    async def _get_json(self, url: str) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            try:
                resp = await client.get(url)
            except httpx.HTTPError as e:
                logger.warning("Package API GET failed: %s", e)
                raise PackageApiUpstreamError("Package API unreachable") from e

        if resp.status_code >= 400:
            raise PackageApiUpstreamError(f"Package API error ({resp.status_code})")
        return resp.json()

    async def _post_json(self, url: str, *, params: dict[str, Any] | None, json: Any | None) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            try:
                resp = await client.post(url, params=params, json=json)
            except httpx.HTTPError as e:
                logger.warning("Package API POST failed: %s", e)
                raise PackageApiUpstreamError("Package API unreachable") from e

        if resp.status_code >= 400:
            raise PackageApiUpstreamError(f"Package API error ({resp.status_code})")
        return resp.json()

