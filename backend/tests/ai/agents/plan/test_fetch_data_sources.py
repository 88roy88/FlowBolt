"""Tests for the plan agent's data-source fetch + file generation."""

from __future__ import annotations

from typing import Any

import pytest

from flow44.ai.agents.plan.agent import PlanAgent
from flow44.logic import data_source as ds_logic
from flow44.logic.models import (
    DataSourceFieldSchema,
    DataSourceParamsInfo,
    DataSourceQuerySchema,
    DataSourceUsage,
    ParamDefinition,
)


def _usage(
    *,
    params: list[ParamDefinition],
    require_any: bool = False,
    minimal: dict[str, Any] | None = None,
    sample: dict[str, Any] | None = None,
) -> DataSourceUsage:
    return DataSourceUsage(
        queries=[
            DataSourceQuerySchema(
                name="rows",
                display_name="Rows",
                description="Rows cube",
                fields=[DataSourceFieldSchema(name="id", display_name="ID", type="Integer")],
            )
        ],
        params=DataSourceParamsInfo(parameters=params, require_any=require_any),
        minimal_params=minimal,
        sample=sample,
    )


class TestFetchAndAnalyze:
    async def test_no_param_data_source(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _name(*_a: object, **_kw: object) -> str:
            return "Weather"

        async def _usage_fn(*_a: object, **_kw: object) -> DataSourceUsage:
            return _usage(
                params=[],
                minimal={},
                sample={"results": {"rows": [{"id": 1}]}},
            )

        async def _analyze(*_a: object, **_kw: object) -> dict[str, str]:
            return {
                "data_schema": "schema",
                "relevant_fields": "id",
                "data_characteristics": "static",
                "integration_notes": "none",
            }

        monkeypatch.setattr(ds_logic, "get_display_name", _name)
        monkeypatch.setattr(ds_logic, "get_usage", _usage_fn)
        monkeypatch.setattr(PlanAgent, "_analyze_data_source", _analyze)

        agent = PlanAgent.__new__(PlanAgent)
        agent._data_source_authorization = None  # type: ignore[attr-defined]
        ctx = await agent._fetch_and_analyze_data_source("42")

        assert ctx["data_source_id"] == "42"
        assert ctx["data_source_name"] == "Weather"
        assert ctx["sanitized_name"] == "Weather"
        assert ctx["can_run_without_input"] is True
        assert ctx["minimal_params"] == {}
        assert ctx["sample_data"] == {"results": {"rows": [{"id": 1}]}}
        assert ctx["params_info"] == {"parameters": [], "require_any": False}

    async def test_params_requiring_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _name(*_a: object, **_kw: object) -> str:
            return "Person by ID"

        async def _usage_fn(*_a: object, **_kw: object) -> DataSourceUsage:
            return _usage(
                params=[
                    ParamDefinition(
                        name="person_id",
                        display_name="Person",
                        type="Integer",
                        is_required=True,
                        is_single_value=True,
                        options=[],
                    )
                ],
                minimal=None,
                sample=None,
            )

        async def _analyze(*_a: object, **_kw: object) -> dict[str, str]:
            return {
                "data_schema": "person",
                "relevant_fields": "id",
                "data_characteristics": "requires input",
                "integration_notes": "form",
                "param_ux_hints": "person_id — user input",
            }

        monkeypatch.setattr(ds_logic, "get_display_name", _name)
        monkeypatch.setattr(ds_logic, "get_usage", _usage_fn)
        monkeypatch.setattr(PlanAgent, "_analyze_data_source", _analyze)

        agent = PlanAgent.__new__(PlanAgent)
        agent._data_source_authorization = None  # type: ignore[attr-defined]
        ctx = await agent._fetch_and_analyze_data_source("7")

        assert ctx["can_run_without_input"] is False
        assert ctx["sample_data"] is None
        assert ctx["minimal_params"] is None
        assert ctx["params_info"]["parameters"][0]["name"] == "person_id"


class TestGenerateDataSourceFiles:
    def test_no_param_emits_single_module(self) -> None:
        ctx = {
            "data_source_id": "42",
            "sanitized_name": "Sales",
            "params_info": {"parameters": [], "require_any": False},
            "queries": [
                {
                    "name": "rows",
                    "display_name": "Rows",
                    "description": "",
                    "fields": [{"name": "id", "display_name": "ID", "type": "Integer", "description": None}],
                }
            ],
            "sample_data": {"results": {"rows": [{"id": 1}]}},
        }
        files = PlanAgent._generate_data_source_files(ctx)
        assert set(files.keys()) == {"src/dataSources/Sales.ts"}
        content = files["src/dataSources/Sales.ts"]
        assert "export async function dataSourceSales()" in content
        assert "fetchWithAuth('/api/data-source/42/run')" in content

    def test_requires_input_emits_typed_signature(self) -> None:
        ctx = {
            "data_source_id": "7",
            "sanitized_name": "Person",
            "params_info": {
                "parameters": [
                    {
                        "name": "person_id",
                        "display_name": "Person",
                        "description": None,
                        "type": "Integer",
                        "is_required": True,
                        "is_single_value": True,
                        "is_require_any": False,
                        "options": [],
                    }
                ],
                "require_any": False,
            },
            "queries": [
                {
                    "name": "person",
                    "display_name": "Person",
                    "description": "",
                    "fields": [{"name": "id", "display_name": "ID", "type": "Integer", "description": None}],
                }
            ],
            "sample_data": None,
        }
        files = PlanAgent._generate_data_source_files(ctx)
        content = files["src/dataSources/Person.ts"]
        assert "export async function dataSourcePerson(personId: number)" in content
        # Schema-based response type since no sample.
        assert "export interface PersonResponse" in content
        assert "body['person_id'] = personId;" in content
