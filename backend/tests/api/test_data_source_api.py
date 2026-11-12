"""Tests for data-source API error mapping and validation."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException
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
                background_tasks=BackgroundTasks(),
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
            background_tasks=BackgroundTasks(),
            params=None,
        )
        assert isinstance(res, JSONResponse)
        assert res.status_code == 502
        assert json.loads(res.body) == upstream_body

    async def test_run_logs_project_and_app_source(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_run(*_a, **_kw):
            return {"data": {}}

        async def _fake_get_project(project_id: str):
            return SimpleNamespace(id=project_id, name="My App")

        events: list[tuple[str, dict]] = []
        monkeypatch.setattr(ds_logic, "run_data_source", _fake_run)
        monkeypatch.setattr(data_source_api, "get_project", _fake_get_project)
        monkeypatch.setattr(data_source_api, "log_bi_event", lambda event, **kw: events.append((event, kw)))

        background_tasks = BackgroundTasks()
        await data_source_api.run_data_source(
            data_source_id="42",
            authorization="Bearer test",
            background_tasks=background_tasks,
            params=None,
            app_project_id="p1",
            app_mode="published",
        )
        await background_tasks()

        assert data_source_api._log_project_id.get() == "p1"
        assert data_source_api._log_project_name.get() == "My App"
        [(event, props)] = events
        assert event == "flapi_call_made"
        assert props["app_source"] == "published"

    async def test_run_ignores_unknown_app_mode_and_missing_project(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_run(*_a, **_kw):
            return {"data": {}}

        async def _no_project(_project_id: str):
            return None

        events: list[tuple[str, dict]] = []
        monkeypatch.setattr(ds_logic, "run_data_source", _fake_run)
        monkeypatch.setattr(data_source_api, "get_project", _no_project)
        monkeypatch.setattr(data_source_api, "log_bi_event", lambda event, **kw: events.append((event, kw)))

        background_tasks = BackgroundTasks()
        await data_source_api.run_data_source(
            data_source_id="42",
            authorization="Bearer test",
            background_tasks=background_tasks,
            params=None,
            app_project_id="missing",
            app_mode="bogus",
        )
        await background_tasks()

        [(_, props)] = events
        assert "app_source" not in props

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
