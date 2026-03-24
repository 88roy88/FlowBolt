"""Tests for data-source API error mapping and validation."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from flow44.api import data_source_api
from flow44.integrations.data_source_cases import DataSourceUpstreamError


class TestDataSourceAPI:
    async def test_data_source_search_maps_validation_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_search(query_or_id: str, *, authorization: str | None):
            raise ValueError("query_or_id is required")

        monkeypatch.setattr(data_source_api, "search_data_sources", _fake_search)

        with pytest.raises(HTTPException) as exc:
            await data_source_api._data_source_search(" ", authorization=None)

        assert exc.value.status_code == 422
        assert exc.value.detail == "query_or_id is required"

    async def test_run_data_source_rejects_empty_id(self) -> None:
        with pytest.raises(HTTPException) as exc:
            await data_source_api._run_data_source("   ", allQueries=None, body=None, authorization=None)
        assert exc.value.status_code == 422
        assert exc.value.detail == "data_source_id is required"

    async def test_run_data_source_maps_unauthorized_upstream(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_run(
            data_source_id: str,
            *,
            authorization: str | None,
            all_queries: bool | None,
            body: object | None,
        ):
            raise DataSourceUpstreamError("upstream unauthorized", status_code=401)

        monkeypatch.setattr(data_source_api, "run_data_source_upstream", _fake_run)

        with pytest.raises(HTTPException) as exc:
            await data_source_api._run_data_source("42", allQueries=True, body=None, authorization="Bearer test")

        assert exc.value.status_code == 401
        assert exc.value.detail == "Data source upstream unauthorized"
