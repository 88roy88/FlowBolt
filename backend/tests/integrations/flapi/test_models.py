"""Unit tests for flow44.integrations.flapi.models — no mock server required."""

from __future__ import annotations

import pytest

from flow44.integrations.flapi.models import PackageMetadata, QuickParamsInfo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE = {
    "DisplayName": "Test param",
    "IsSingleValue": True,
    "IsRequired": False,
    "IsRequireAny": False,
}


def _param(name: str, type_: str, value: object) -> dict:
    return {**_BASE, "Name": name, "Type": type_, "Value": value}


def _info(params: list[dict]) -> QuickParamsInfo:
    return QuickParamsInfo.model_validate({"cube1": params})


# ---------------------------------------------------------------------------
# ParamType normalisation
# ---------------------------------------------------------------------------


class TestParamTypeNormalisation:
    @pytest.mark.parametrize("raw_type", ["int", "Int", "INT"])
    def test_int_variants_all_parse(self, raw_type: str) -> None:
        result = _info([_param("count", raw_type, 0)])
        assert result.root["cube1"][0].type_ == "Int"

    @pytest.mark.parametrize("raw_type", ["string", "String"])
    def test_string_variants_all_parse(self, raw_type: str) -> None:
        result = _info([_param("label", raw_type, "hello")])
        assert result.root["cube1"][0].type_ == "String"


# ---------------------------------------------------------------------------
# Option-item values  {Name: str, Value: str | int | float}
# ---------------------------------------------------------------------------


class TestOptionValueItem:
    def test_string_value_parses(self) -> None:
        result = _info([_param("status", "String", {"Name": "Active", "Value": "active"})])
        item = result.root["cube1"][0].value
        assert item.Name == "Active"  # type: ignore[union-attr]
        assert item.Value == "active"  # type: ignore[union-attr]

    def test_int_value_parses(self) -> None:
        result = _info([_param("count", "Int", {"Name": "Ten", "Value": 10})])
        item = result.root["cube1"][0].value
        assert item.Value == 10  # type: ignore[union-attr]

    def test_float_value_parses(self) -> None:
        result = _info([_param("ratio", "Double", {"Name": "Half", "Value": 0.5})])
        item = result.root["cube1"][0].value
        assert item.Value == 0.5  # type: ignore[union-attr]

    def test_list_of_option_items_parses(self) -> None:
        value = [{"Name": "A", "Value": "a"}, {"Name": "B", "Value": "b"}]
        result = _info([_param("tag", "String", value)])
        assert len(result.root["cube1"][0].value) == 2  # type: ignore[arg-type]

    def test_null_name_and_value_parses(self) -> None:
        result = _info([_param("tag", "String", {"Name": None, "Value": None})])
        item = result.root["cube1"][0].value
        assert item.Name is None  # type: ignore[union-attr]
        assert item.Value is None  # type: ignore[union-attr]

    def test_null_option_in_list_parses(self) -> None:
        value = [{"Name": None, "Value": None}, {"Name": "active", "Value": "yes"}]
        result = _info([_param("status", "String", value)])
        assert len(result.root["cube1"][0].value) == 2  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Haphoch param with geo-object option items
# {Name: str | None, Type: str, Value: <complex geo object>}
# ---------------------------------------------------------------------------

_GEO_OBJECT = {
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [34.8, 31.6]},
}


class TestGeoOptionValueItem:
    def test_haphoch_with_geo_option_list_parses(self) -> None:
        value = [{"Name": "Tel Aviv", "Type": "wkt", "Value": _GEO_OBJECT}]
        result = _info([_param("area", "Haphoch", value)])
        param = result.root["cube1"][0]
        assert param.type_ == "Haphoch"
        assert isinstance(param.value, list)
        assert param.value[0].Name == "Tel Aviv"  # type: ignore[union-attr]

    def test_geo_type_field_is_preserved(self) -> None:
        value = [{"Name": "Circle", "Type": "geoellipse", "Value": _GEO_OBJECT}]
        result = _info([_param("zone", "Haphoch", value)])
        item = result.root["cube1"][0].value[0]  # type: ignore[index]
        assert item.Type == "geoellipse"  # type: ignore[union-attr]

    def test_null_name_is_allowed(self) -> None:
        value = [{"Name": None, "Type": "wkt", "Value": _GEO_OBJECT}]
        result = _info([_param("area", "Haphoch", value)])
        assert result.root["cube1"][0].value[0].Name is None  # type: ignore[index,union-attr]


# ---------------------------------------------------------------------------
# Unknown FieldType (PackageMetadata) and ParamType (QuickParamsInfo)
# ---------------------------------------------------------------------------

_QUERY_BASE = {
    "uniqueName": "q1",
    "originalName": "q1",
    "Name": "Query 1",
    "ResultsLimit": 100,
    "DataSourceName": "ds",
    "Description": "desc",
    "id": "q1",
}


def _package_with_field_type(field_type: str) -> dict:
    return {
        "Id": 1,
        "Name": "pkg",
        "Description": "desc",
        "Queries": [
            {
                **_QUERY_BASE,
                "Fields": [
                    {"Name": "col", "DisplayName": "Col", "Type": field_type},
                ],
            }
        ],
    }


class TestPackageMetadataFieldType:
    def test_unknown_field_type_does_not_raise(self) -> None:
        result = PackageMetadata.model_validate(_package_with_field_type("html"))
        assert result.queries[0].fields[0].type_ == "html"


class TestPackageMetadataDescription:
    def test_null_description_does_not_raise(self) -> None:
        payload = _package_with_field_type("string")
        payload["Description"] = None
        result = PackageMetadata.model_validate(payload)
        assert result.description is None


class TestQuickParamUnknownType:
    def test_unknown_param_type_does_not_raise(self) -> None:
        result = _info([_param("x", "Geospatial", "some_value")])
        assert result.root["cube1"][0].type_ == "Geospatial"
