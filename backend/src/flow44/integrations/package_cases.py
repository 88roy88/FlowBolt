from __future__ import annotations

from typing import Any

from flow44.config import settings
from flow44.integrations.flapi_api import FlapiClient


def normalize_package_authorization(raw: str | None) -> str | None:
    if raw is None:
        return None
    token = raw.strip()
    return token or None


def _client(*, authorization: str | None) -> FlapiClient:
    return FlapiClient(
        base_url=settings.FLAPI_BASE_URL,
        authorization=normalize_package_authorization(authorization),
    )


async def search_packages(query_or_id: str, *, authorization: str | None) -> list[Any]:
    if not query_or_id.strip():
        raise ValueError("query_or_id is required")
    return await _client(authorization=authorization).search(query_or_id)


async def get_case_display_name(case_id: int, *, authorization: str | None) -> str:
    fallback = f"Case #{case_id}"
    results = await search_packages(str(case_id), authorization=authorization)
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


async def fetch_case_package_data(
    package_id: str,
    *,
    authorization: str | None,
) -> tuple[str, Any]:
    results = await search_packages(package_id, authorization=authorization)
    if not results:
        raise LookupError(f"Package {package_id} not found")

    metadata = results[0]
    package_name = (
        metadata.get("Name", f"Package {package_id}") if isinstance(metadata, dict) else f"Package {package_id}"
    )
    sample_data = await _client(authorization=authorization).run_package(
        package_id,
        all_queries=True,
        body=None,
    )
    return package_name, sample_data
