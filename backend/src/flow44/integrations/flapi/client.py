import logging
from typing import Any
from urllib.parse import quote

import httpx

from flow44.config import settings
from flow44.integrations.flapi.models import (
    DataSourceRunResult,
    PackageMetadata,
    PackageSearchResult,
    QuickParams,
    QuickParamsInfo,
)

logger = logging.getLogger(__name__)

__all__ = ["FlapiClient", "FlapiUpstreamError", "data_source_client"]


class FlapiUpstreamError(RuntimeError):
    """FLAPI returned an error or was unreachable."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class FlapiClient:
    def __init__(self, base_url: str | None = None, *, timeout_s: float = 30.0) -> None:
        self.base_url = base_url or settings.FLAPI_BASE_URL
        self._http = httpx.AsyncClient(
            base_url=self.base_url.rstrip("/"),
            timeout=timeout_s,
            verify=settings.FLAPI_VERIFY_SSL,
        )

    @staticmethod
    def _build_auth_header(authorization: str | None) -> dict[str, str]:
        token = (authorization.strip() or None) if authorization else None
        if not token:
            return {}
        return {"Authorization": token}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        authorization: str | None = None,
        body: Any | None = None,
        **kwargs: Any,
    ) -> Any:
        try:
            resp = await self._http.request(
                method,
                path,
                headers=self._build_auth_header(authorization),
                json=body,
                **kwargs,
            )
        except httpx.HTTPError as exc:
            logger.warning("FLAPI %s %s failed: %s", method, path, exc)
            hint = (
                f"Cannot connect to FLAPI at {self.base_url} ({type(exc).__name__}: {exc}). "
                "For local dev, start the mock: cd mocks/flapi-mock && pnpm start (port 6001 by default)."
            )
            raise FlapiUpstreamError(hint) from exc

        if resp.status_code >= 500:
            # Truncate body: responses can be large and may include sensitive fields.
            logger.error(
                "FLAPI %s on %s %s: %s",
                resp.status_code, method, path, resp.text[:500],
            )
        elif resp.status_code >= 400:
            logger.info("FLAPI %s on %s %s", resp.status_code, method, path)
        if resp.status_code >= 400:
            raise FlapiUpstreamError(
                f"FLAPI error ({resp.status_code})", status_code=resp.status_code
            )
        return resp.json()

    # -- API methods --

    async def search(
        self, query_or_id: str | int, *, authorization: str | None = None
    ) -> list[PackageSearchResult]:
        safe = quote(str(query_or_id), safe="")
        raw: list[dict[str, Any]] = await self._request(
            "GET", f"/package/v1/search/{safe}", authorization=authorization
        )
        return [PackageSearchResult.model_validate(item) for item in raw]

    async def run_data_source(
        self,
        data_source_id: str | int,
        *,
        authorization: str | None = None,
        all_queries: bool | None = None,
        execute_continued_process: bool | None = None,
        quick_params: QuickParams | None = None,
    ) -> DataSourceRunResult:
        queryParams: dict[str, str] = {}
        queryParams["allQueries"] = "true"
        # if all_queries is not None:
        if execute_continued_process is not None:
            queryParams["executeContinuedProcess"] = "true" if execute_continued_process else "false"
        safe = quote(str(data_source_id), safe="")
        body = quick_params.model_dump() if quick_params else {}
        raw: dict[str, Any] = await self._request(
            "POST",
            f"/package/v3/{safe}",
            authorization=authorization,
            body=body,
            params=queryParams,
        )
        return DataSourceRunResult.model_validate(raw)

    async def get_quick_params_info(
        self, data_source_id: str | int, *, authorization: str | None = None
    ) -> QuickParamsInfo:
        safe = quote(str(data_source_id), safe="")
        raw: dict[str, Any] = await self._request(
            "GET", f"/package/v1/quick/{safe}", authorization=authorization
        )
        return QuickParamsInfo.model_validate(raw)

    async def get_metadata(
        self, data_source_id: str | int, *, authorization: str | None = None
    ) -> PackageMetadata:
        safe = quote(str(data_source_id), safe="")
        raw: dict[str, Any] = await self._request(
            "GET", f"/package/v2/{safe}", authorization=authorization
        )
        return PackageMetadata.model_validate(raw)


# Module-level singleton — reuses TCP connections across requests.
data_source_client = FlapiClient()
