"""FLAPI client — proxies package search and execution to the upstream service.

This module intentionally keeps all upstream (FLAPI) HTTP concerns isolated:
timeouts, error mapping, and URL construction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

logger = logging.getLogger(__name__)


class FlapiUpstreamError(RuntimeError):
    """Raised when the upstream FLAPI returns an error or is unreachable."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class FlapiClient:
    base_url: str
    timeout_s: float = 20.0
    # Sent as Authorization header to FLAPI (e.g. Bearer token from the browser).
    authorization: str | None = None

    def _base_url_without_ssl(self) -> str:
        """Normalize base URL to non-SSL transport for FLAPI."""
        raw_base = self.base_url.strip()
        parts = urlsplit(raw_base)
        if parts.scheme == "https":
            logger.info("FLAPI base URL uses https; downgrading to http: %s", raw_base)
            return urlunsplit(("http", parts.netloc, parts.path, parts.query, parts.fragment))
        return raw_base

    def _url(self, path: str) -> str:
        return f"{self._base_url_without_ssl().rstrip('/')}{path}"

    def _upstream_headers(self) -> dict[str, str]:
        if self.authorization is None:
            return {}
        token = self.authorization.strip()
        if not token:
            return {}
        return {"Authorization": token}

    async def search(self, query_or_id: str) -> list[Any]:
        safe = quote(str(query_or_id), safe="")
        url = self._url(f"/package/v1/search/{safe}")
        result: list[Any] = await self._get_json(url)
        return result

    async def run_data_source(
        self,
        data_source_id: str,
        *,
        all_queries: bool | None,
        body: Any | None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if all_queries is not None:
            # Upstream uses allQueries=true/false
            params["allQueries"] = "true" if all_queries else "false"
        safe = quote(str(data_source_id), safe="")
        url = self._url(f"/package/v3/{safe}")
        result: dict[str, Any] = await self._post_json(url, params=params, json=body)
        return result

    async def _get_json(self, url: str) -> Any:
        headers = self._upstream_headers()
        # FLAPI in this environment is intentionally called without SSL verification.
        async with httpx.AsyncClient(timeout=self.timeout_s, verify=False) as client:  # noqa: S501
            try:
                resp = await client.get(url, headers=headers or None)
            except httpx.HTTPError as e:
                logger.warning("FLAPI GET failed: %s", e)
                raise FlapiUpstreamError("FLAPI unreachable") from e

        if resp.status_code >= 400:
            raise FlapiUpstreamError(
                f"FLAPI error ({resp.status_code})",
                status_code=resp.status_code,
            )
        return resp.json()

    async def _post_json(self, url: str, *, params: dict[str, Any] | None, json: Any | None) -> Any:
        headers = self._upstream_headers()
        # FLAPI in this environment is intentionally called without SSL verification.
        async with httpx.AsyncClient(timeout=self.timeout_s, verify=False) as client:  # noqa: S501
            try:
                resp = await client.post(url, params=params, json=json, headers=headers or None)
            except httpx.HTTPError as e:
                logger.warning("FLAPI POST failed: %s", e)
                raise FlapiUpstreamError("FLAPI unreachable") from e

        if resp.status_code >= 400:
            raise FlapiUpstreamError(
                f"FLAPI error ({resp.status_code})",
                status_code=resp.status_code,
            )
        return resp.json()
