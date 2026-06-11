"""Tests for the plan agent's data-source fetch + file generation."""

from __future__ import annotations

from typing import Any

import pytest

from flow44.ai.agents import analyze_data_source as ads_module
from flow44.ai.agents.analyze_data_source import fetch_and_analyze_data_source, generate_data_source_files
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
                fields=[DataSourceFieldSchema(name="id", display_name="ID", type="int")],
            )
        ],
        params=DataSourceParamsInfo(parameters=params, require_any=require_any),
        can_run=minimal is not None,
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

        analysis = {
            "data_schema": "schema",
            "relevant_fields": "id",
            "data_characteristics": "static",
            "integration_notes": "none",
        }

        async def _complete_chat(*_a: object, **_kw: object) -> str:
            return ""

        monkeypatch.setattr(ds_logic, "get_display_name", _name)
        monkeypatch.setattr(ds_logic, "get_usage", _usage_fn)
        monkeypatch.setattr(ads_module, "complete_chat", _complete_chat)
        monkeypatch.setattr(ads_module, "parse_json_response", lambda _: analysis)

        ctx = await fetch_and_analyze_data_source("42", "", None, None, lambda _: {})

        assert ctx["data_source_id"] == "42"
        assert ctx["data_source_name"] == "Weather"
        assert ctx["sanitized_name"] == "Weather"
        assert ctx["can_run_without_input"] is True
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
                        type="int",
                        is_required=True,
                        is_single_value=True,
                        options=[],
                    )
                ],
                minimal=None,
                sample=None,
            )

        analysis = {
            "data_schema": "person",
            "relevant_fields": "id",
            "data_characteristics": "requires input",
            "integration_notes": "form",
            "param_ux_hints": "person_id — user input",
        }

        async def _complete_chat(*_a: object, **_kw: object) -> str:
            return ""

        monkeypatch.setattr(ds_logic, "get_display_name", _name)
        monkeypatch.setattr(ds_logic, "get_usage", _usage_fn)
        monkeypatch.setattr(ads_module, "complete_chat", _complete_chat)
        monkeypatch.setattr(ads_module, "parse_json_response", lambda _: analysis)

        ctx = await fetch_and_analyze_data_source("7", "", None, None, lambda _: {})

        assert ctx["can_run_without_input"] is False
        assert ctx["sample_data"] is None
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
                    "fields": [{"name": "id", "display_name": "ID", "type": "int", "description": None}],
                }
            ],
            "sample_data": {"results": {"rows": [{"id": 1}]}},
        }
        files = generate_data_source_files(ctx)
        assert set(files.keys()) == {"src/dataSources/Sales.ts", "src/dataSources/Sales.docs.md"}
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
                        "type": "int",
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
                    "fields": [{"name": "id", "display_name": "ID", "type": "int", "description": None}],
                }
            ],
            "sample_data": None,
        }
        files = generate_data_source_files(ctx)
        content = files["src/dataSources/Person.ts"]
        assert "}: {\n  personId: number; // Person\n}): Promise<PersonResults>" in content
        assert "export interface PersonPerson" in content
        assert "export interface PersonResults" in content
        assert "body['']['person_id'] = personId;" in content
