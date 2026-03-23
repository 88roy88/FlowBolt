"""FLAPI client — proxies package search and execution to the upstream service.

This module intentionally keeps all upstream (FLAPI) HTTP concerns isolated:
timeouts, error mapping, and URL construction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


class FlapiUpstreamError(RuntimeError):
    """Raised when the upstream FLAPI returns an error or is unreachable."""


@dataclass(frozen=True, slots=True)
class FlapiClient:
    base_url: str
    timeout_s: float = 20.0

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    async def search(self, query_or_id: str) -> list[Any]:
        safe = quote(str(query_or_id), safe="")
        url = self._url(f"/package/v1/search/{safe}")
        result: list[Any] = await self._get_json(url)
        return result

    async def run_package(self, package_id: str, *, all_queries: bool | None, body: Any | None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if all_queries is not None:
            # Upstream uses allQueries=true/false
            params["allQueries"] = "true" if all_queries else "false"
        safe = quote(str(package_id), safe="")
        url = self._url(f"/package/v3/{safe}")
        result: dict[str, Any] = await self._post_json(url, params=params, json=body)
        return result

    async def _get_json(self, url: str) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            try:
                resp = await client.get(url)
            except httpx.HTTPError as e:
                logger.warning("FLAPI GET failed: %s", e)
                raise FlapiUpstreamError("FLAPI unreachable") from e

        if resp.status_code >= 400:
            raise FlapiUpstreamError(f"FLAPI error ({resp.status_code})")
        return resp.json()

    async def _post_json(self, url: str, *, params: dict[str, Any] | None, json: Any | None) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            try:
                resp = await client.post(url, params=params, json=json)
            except httpx.HTTPError as e:
                logger.warning("FLAPI POST failed: %s", e)
                raise FlapiUpstreamError("FLAPI unreachable") from e

        if resp.status_code >= 400:
            raise FlapiUpstreamError(f"FLAPI error ({resp.status_code})")
        return resp.json()
