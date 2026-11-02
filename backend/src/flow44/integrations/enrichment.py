import functools
import logging

import httpx

from flow44.config import settings

logger = logging.getLogger(__name__)

__all__ = ["fetch_data_source_summary"]


@functools.cache
def _warn_missing_url() -> None:
    logger.warning("AIB_DATA_SOURCE_ENRICHMENT_URL is not set, skipping data source enrichment")


async def fetch_data_source_summary(data_source_id: str) -> str:
    url = settings.DATA_SOURCE_ENRICHMENT_URL
    if not url:
        _warn_missing_url()
        return ""

    if not data_source_id.isdecimal():
        logger.error("Invalid data source id %r, must be a number", data_source_id)
        return ""
    package_id = int(data_source_id)

    try:
        async with httpx.AsyncClient(timeout=settings.DATA_SOURCE_ENRICHMENT_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json={"packageId": package_id})
            response.raise_for_status()
            summary = response.json().get("package_summary")
    except (httpx.HTTPError, ValueError, AttributeError) as exc:
        logger.error("Data source enrichment failed for package %s: %s", package_id, exc)
        return ""

    return summary.strip() if isinstance(summary, str) else ""
