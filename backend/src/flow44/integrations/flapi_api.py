import logging
from typing import Any
from urllib.parse import quote

import httpx

from flow44.config import settings

logger = logging.getLogger(__name__)


class FlapiUpstreamError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class FlapiClient:
    def __init__(self, base_url: str | None = None, *, timeout_s: float = 30.0) -> None:
        self.base_url = base_url or settings.FLAPI_BASE_URL
        self._http = httpx.AsyncClient(
            base_url=self.base_url.rstrip("/"),
            timeout=timeout_s,
            verify=settings.VERIFY_FLAPI_SSL,
        )

    @staticmethod
    def _auth_header(authorization: str | None) -> dict[str, str]:
        token = (authorization.strip() or None) if authorization else None
        return {"Authorization": token} if token else {}

    async def _request(self, method: str, path: str, *, authorization: str | None = None, **kwargs: Any) -> Any:
        try:
            resp = await self._http.request(method, path, headers=self._auth_header(authorization), **kwargs)
        except httpx.HTTPError as exc:
            logger.warning("FLAPI %s %s failed: %s", method, path, exc)
            raise FlapiUpstreamError("FLAPI unreachable") from exc

        if resp.status_code >= 400:
            raise FlapiUpstreamError(f"FLAPI error ({resp.status_code})", status_code=resp.status_code)
        return resp.json()

    # -- API methods --

    async def search(self, query_or_id: str, *, authorization: str | None = None) -> list[Any]:
        safe = quote(str(query_or_id), safe="")
        result: list[Any] = await self._request("GET", f"/package/v1/search/{safe}", authorization=authorization)
        return result

    async def run_data_source(
        self,
        data_source_id: str,
        *,
        authorization: str | None = None,
        all_queries: bool | None = None,
        execute_continued_process: bool | None = None,
        body: Any | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if all_queries is not None:
            params["allQueries"] = "true" if all_queries else "false"
        if execute_continued_process is not None:
            params["executeContinuedProcess"] = "true" if execute_continued_process else "false"
        safe = quote(str(data_source_id), safe="")
        result: dict[str, Any] = await self._request(
            "POST",
            f"/package/v3/{safe}",
            authorization=authorization,
            params=params,
            json=body,
        )
        return result

    # -- High-level helpers --

    async def get_display_name(self, data_source_id: int | str, *, authorization: str | None = None) -> str:
        results = await self.search(str(data_source_id), authorization=authorization)
        if not results or not isinstance(results[0], dict) or "Name" not in results[0]:
            raise LookupError("Failed to get display name for data source %s: not found", data_source_id)
        name: str = results[0]["Name"].strip()
        return name

    async def fetch_data_source(
        self,
        data_source_id: str,
        *,
        authorization: str | None = None,
    ) -> tuple[str, Any]:
        name = await self.get_display_name(data_source_id, authorization=authorization)
        sample_data = await self.run_data_source(
            data_source_id,
            authorization=authorization,
            all_queries=True,
            execute_continued_process=False,
        )
        return name, sample_data


# Module-level singleton — reuses TCP connections across requests
data_source_client = FlapiClient()
