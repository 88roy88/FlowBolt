"""Tests for data-source API error mapping and validation."""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from flow44.api import data_source_api
from flow44.logic import data_source as ds_logic


class TestDataSourceAPI:
    async def test_run_maps_401_upstream(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_run(*_a, **_kw):
            raise ds_logic.FlapiUpstreamError("unauthorized", status_code=401)

        monkeypatch.setattr(ds_logic, "run_data_source", _fake_run)

        with pytest.raises(HTTPException) as exc:
            await data_source_api.run_data_source(
                data_source_id="42",
                authorization="Bearer test",
                params=None,
            )
        assert exc.value.status_code == 401

    async def test_run_passes_upstream_json_body_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        upstream_body = {"error": "Parameter 'person_id' is required"}

        async def _fake_run(*_a, **_kw):
            raise ds_logic.FlapiUpstreamError("FLAPI error (400)", status_code=400, body=upstream_body)

        monkeypatch.setattr(ds_logic, "run_data_source", _fake_run)

        res = await data_source_api.run_data_source(
            data_source_id="42",
            authorization="Bearer test",
            params=None,
        )
        assert isinstance(res, JSONResponse)
        assert res.status_code == 502
        assert json.loads(res.body) == upstream_body

    async def test_search_maps_500_to_502(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_search(*_a, **_kw):
            raise ds_logic.FlapiUpstreamError("FLAPI error (500)", status_code=500)

        monkeypatch.setattr(ds_logic, "search_data_sources", _fake_search)

        with pytest.raises(HTTPException) as exc:
            await data_source_api.search_data_source(
                query_or_id="test",
                authorization=None,
            )
        assert exc.value.status_code == 502
