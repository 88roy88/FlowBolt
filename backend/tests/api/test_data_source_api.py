"""Tests for data-source API error mapping and validation."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from flow44.api import data_source_api
from flow44.integrations.flapi_api import FlapiUpstreamError


class TestDataSourceAPI:
    async def test_run_maps_401_upstream(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_run(*_a, **_kw):  # noqa: ANN002, ANN003
            raise FlapiUpstreamError("unauthorized", status_code=401)

        monkeypatch.setattr(data_source_api.data_source_client, "run_data_source", _fake_run)

        with pytest.raises(HTTPException) as exc:
            await data_source_api.run_data_source("42", authorization="test-token")
        assert exc.value.status_code == 401

    async def test_search_maps_500_to_502(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_search(*_a, **_kw):  # noqa: ANN002, ANN003
            raise FlapiUpstreamError("FLAPI error (500)", status_code=500)

        monkeypatch.setattr(data_source_api.data_source_client, "search", _fake_search)

        with pytest.raises(HTTPException) as exc:
            await data_source_api.search_data_source("test", authorization=None)
        assert exc.value.status_code == 502
