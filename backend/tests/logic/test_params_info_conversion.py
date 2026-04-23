# Tests for the FLAPI -> domain conversion performed by logic.data_source.
# The seam between FlapiClient.get_quick_params_info and DataSourceParamsInfo
# is the place where wire-format drift bites; these tests pin it.
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from flow44.integrations.flapi import models as flapi_models
from flow44.logic import data_source as ds_logic


def _flapi_info(
    *params: flapi_models.QuickParamDefinition,
    query_id: str = "q1",
) -> flapi_models.QuickParamsInfo:
    return flapi_models.QuickParamsInfo(root={query_id: list(params)})


def _param(
    name: str,
    *,
    type_: str = "String",
    is_required: bool = False,
    is_single_value: bool = True,
    is_require_any: bool = False,
    options: list[tuple[str, str]] | None = None,
    description: str | None = None,
) -> flapi_models.QuickParamDefinition:
    return flapi_models.QuickParamDefinition.model_validate({
        "Name": name,
        "DisplayName": name.title(),
        "Description": description,
        "Type": type_,
        "OntologyType": "TEXT",
        "IsSingleValue": is_single_value,
        "IsRequired": is_required,
        "IsRequireAny": is_require_any,
        "Value": [{"Name": n, "Value": v} for n, v in (options or [])],
    })


class TestToParamsInfo:
    async def test_preserves_flat_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        info = _flapi_info(
            _param("status", is_required=True, options=[("Active", "Active")]),
        )
        monkeypatch.setattr(
            ds_logic.data_source_client, "get_quick_params_info", AsyncMock(return_value=info)
        )

        result = await ds_logic.get_params_info("1")
        assert len(result.parameters) == 1
        p = result.parameters[0]
        assert p.name == "status"
        assert p.display_name == "Status"
        assert p.type == "string"
        assert p.is_required is True
        assert p.is_single_value is True
        assert p.is_require_any is False
        assert [(o.name, o.value) for o in p.options] == [("Active", "Active")]

    async def test_require_any_lifted_to_outer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        info = _flapi_info(
            _param("region", is_require_any=True, options=[("North", "North")]),
            _param("dept", is_require_any=True, options=[]),
        )
        monkeypatch.setattr(
            ds_logic.data_source_client, "get_quick_params_info", AsyncMock(return_value=info)
        )

        result = await ds_logic.get_params_info("1")
        assert result.require_any is True
        assert all(p.is_require_any for p in result.parameters)

    async def test_require_any_false_when_no_param_has_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        info = _flapi_info(_param("status", is_required=True, options=[("A", "A")]))
        monkeypatch.setattr(
            ds_logic.data_source_client, "get_quick_params_info", AsyncMock(return_value=info)
        )

        result = await ds_logic.get_params_info("1")
        assert result.require_any is False

    async def test_empty_params_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            ds_logic.data_source_client,
            "get_quick_params_info",
            AsyncMock(return_value=flapi_models.QuickParamsInfo(root={})),
        )

        result = await ds_logic.get_params_info("1")
        assert result.parameters == []
        assert result.require_any is False

    async def test_multiple_queries_flattened(self, monkeypatch: pytest.MonkeyPatch) -> None:
        info = flapi_models.QuickParamsInfo(
            root={
                "q1": [_param("a")],
                "q2": [_param("b"), _param("c")],
            }
        )
        monkeypatch.setattr(
            ds_logic.data_source_client, "get_quick_params_info", AsyncMock(return_value=info)
        )

        result = await ds_logic.get_params_info("1")
        assert sorted(p.name for p in result.parameters) == ["a", "b", "c"]

    async def test_nullable_description_survives(self, monkeypatch: pytest.MonkeyPatch) -> None:
        info = _flapi_info(_param("status", description=None))
        monkeypatch.setattr(
            ds_logic.data_source_client, "get_quick_params_info", AsyncMock(return_value=info)
        )

        result = await ds_logic.get_params_info("1")
        assert result.parameters[0].description is None
