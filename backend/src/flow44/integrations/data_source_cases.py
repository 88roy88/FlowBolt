from __future__ import annotations

from typing import Any

from flow44.config import settings
from flow44.integrations.flapi_api import FlapiClient


def normalize_flapi_authorization(raw: str | None) -> str | None:
    if raw is None:
        return None
    token = raw.strip()
    return token or None


def _client(*, authorization: str | None) -> FlapiClient:
    return FlapiClient(
        base_url=settings.FLAPI_BASE_URL,
        authorization=normalize_flapi_authorization(authorization),
    )


async def search_data_sources(query_or_id: str, *, authorization: str | None) -> list[Any]:
    if not query_or_id.strip():
        raise ValueError("query_or_id is required")
    return await _client(authorization=authorization).search(query_or_id)


async def get_data_source_display_name(data_source_id: int, *, authorization: str | None) -> str:
    fallback = f"Data source #{data_source_id}"
    results = await search_data_sources(str(data_source_id), authorization=authorization)
    if not results:
        return fallback

    metadata = results[0]
    if isinstance(metadata, dict):
        raw_name = metadata.get("Name")
        if isinstance(raw_name, str):
            name = raw_name.strip()
            if name:
                return name

    return fallback


async def fetch_data_source_data(
    data_source_id: str,
    *,
    authorization: str | None,
) -> tuple[str, Any]:
    results = await search_data_sources(data_source_id, authorization=authorization)
    if not results:
        raise LookupError(f"Data source {data_source_id} not found")

    metadata = results[0]
    data_source_name = (
        metadata.get("Name", f"Data source {data_source_id}")
        if isinstance(metadata, dict)
        else f"Data source {data_source_id}"
    )
    sample_data = await _client(authorization=authorization).run_data_source(
        data_source_id,
        all_queries=True,
        body=None,
    )
    return data_source_name, sample_data
