# Contract tests: catches wire-format drift between mocks/flapi-mock/schemas.ts
# and flapi/models.py. Skipped when the mock isn't running locally.
from __future__ import annotations

import httpx
import pytest

from flow44.integrations.flapi.models import (
    PackageMetadata,
    PackageSearchResult,
    QuickParamsInfo,
)

MOCK_BASE_URL = "http://localhost:6001"
AUTH = {"Authorization": "a"}
PACKAGE_IDS = [1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 22, 23, 24]


def _mock_is_up() -> bool:
    try:
        r = httpx.get(f"{MOCK_BASE_URL}/health", timeout=0.5)
    except httpx.HTTPError:
        return False
    return r.status_code == 200


pytestmark = pytest.mark.skipif(
    not _mock_is_up(),
    reason="flapi-mock not running on :6001 (cd mocks/flapi-mock && pnpm start)",
)


@pytest.mark.parametrize("package_id", PACKAGE_IDS)
def test_search_parses(package_id: int) -> None:
    r = httpx.get(f"{MOCK_BASE_URL}/package/v1/search/{package_id}", headers=AUTH)
    r.raise_for_status()
    items = [PackageSearchResult.model_validate(x) for x in r.json()]
    assert items
    assert items[0].id_ == package_id


@pytest.mark.parametrize("package_id", PACKAGE_IDS)
def test_quick_params_info_parses(package_id: int) -> None:
    r = httpx.get(f"{MOCK_BASE_URL}/package/v1/quick/{package_id}", headers=AUTH)
    r.raise_for_status()
    QuickParamsInfo.model_validate(r.json())


@pytest.mark.parametrize("package_id", PACKAGE_IDS)
def test_metadata_parses(package_id: int) -> None:
    r = httpx.get(f"{MOCK_BASE_URL}/package/v3/{package_id}", headers=AUTH)
    r.raise_for_status()
    meta = PackageMetadata.model_validate(r.json())
    assert meta.id_ == package_id
