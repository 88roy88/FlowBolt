from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from flow44.integrations.flapi import models as flapi_models
from flow44.logic import data_source as ds_logic
from flow44.logic.models import DataSourceParamsInfo


def _metadata(*, queries: list[flapi_models.Query]) -> flapi_models.PackageMetadata:
    return flapi_models.PackageMetadata.model_validate({
        "Id": 1,
        "Name": "test",
        "Description": "",
        "OutputQueriesId": [],
        "Queries": [q.model_dump(by_alias=True) for q in queries],
    })


def _query(name: str = "q") -> flapi_models.Query:
    return flapi_models.Query.model_validate({
        "uniqueName": f"unique-{name}",
        "originalName": name,
        "Name": name,
        "ResultsLimit": 1000,
        "DataSourceName": "test",
        "Description": "",
        "id": f"id-{name}",
        "Fields": [],
    })


class TestGetUsage:
    async def test_raises_when_metadata_has_no_queries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            ds_logic.data_source_client,
            "get_metadata",
            AsyncMock(return_value=_metadata(queries=[])),
        )

        with pytest.raises(ds_logic.FlapiUpstreamError, match="no queries"):
            await ds_logic.get_usage("1")

    async def test_populates_params_alongside_queries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            ds_logic.data_source_client,
            "get_metadata",
            AsyncMock(return_value=_metadata(queries=[_query("persons")])),
        )

        async def _fake_params(*_a, **_kw):  # noqa: ANN001, ANN002, ANN003, ARG001
            return DataSourceParamsInfo(parameters=[], require_any=False)

        monkeypatch.setattr(ds_logic, "get_params_info", _fake_params)

        usage = await ds_logic.get_usage("1")
        assert len(usage.queries) == 1
        assert usage.queries[0].name == "persons"
        assert usage.params.parameters == []
        assert usage.minimal_params == {}
        assert usage.can_run is True

    async def test_fetches_params_info_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Regression guard: planner used to double-call get_usage + get_params_info.
        # get_usage should call get_params_info exactly once internally.
        monkeypatch.setattr(
            ds_logic.data_source_client,
            "get_metadata",
            AsyncMock(return_value=_metadata(queries=[_query()])),
        )
        params_mock = AsyncMock(
            return_value=DataSourceParamsInfo(parameters=[], require_any=False)
        )
        monkeypatch.setattr(ds_logic, "get_params_info", params_mock)

        await ds_logic.get_usage("1")
        assert params_mock.await_count == 1
