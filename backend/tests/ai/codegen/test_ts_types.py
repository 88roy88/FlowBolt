"""Tests for flow44.ai.codegen.ts_types."""

from __future__ import annotations

from flow44.ai.codegen.ts_types import (
    generate_ts_interfaces,
    sanitize_to_pascal_case,
)


# ---------------------------------------------------------------------------
# sanitize_to_pascal_case
# ---------------------------------------------------------------------------


class TestSanitizeToPascalCase:
    def test_simple_words(self) -> None:
        assert sanitize_to_pascal_case("Weather Forecast API") == "WeatherForecastAPI"

    def test_underscores_and_hyphens(self) -> None:
        assert sanitize_to_pascal_case("my-data_source 2") == "MyDataSource2"

    def test_all_caps(self) -> None:
        assert sanitize_to_pascal_case("SALES") == "SALES"

    def test_single_word(self) -> None:
        assert sanitize_to_pascal_case("orders") == "Orders"

    def test_empty_string(self) -> None:
        assert sanitize_to_pascal_case("") == ""

    def test_only_special_chars(self) -> None:
        assert sanitize_to_pascal_case("---") == ""

    def test_numbers_only(self) -> None:
        assert sanitize_to_pascal_case("42") == "42"

    def test_mixed_separators(self) -> None:
        assert sanitize_to_pascal_case("foo__bar--baz  qux") == "FooBarBazQux"


# ---------------------------------------------------------------------------
# generate_ts_interfaces — list responses
# ---------------------------------------------------------------------------


class TestGenerateTsInterfacesList:
    def test_array_of_objects(self) -> None:
        sample = [{"id": 1, "name": "Alice", "active": True}]
        result = generate_ts_interfaces(sample, "Users")
        assert "export interface UsersRecord" in result
        assert "id: number;" in result
        assert "name: string;" in result
        assert "active: boolean;" in result
        assert "export type UsersResponse = UsersRecord[];" in result

    def test_empty_array(self) -> None:
        result = generate_ts_interfaces([], "Empty")
        assert "export type EmptyRecord = unknown;" in result
        assert "export type EmptyResponse = EmptyRecord[];" in result

    def test_array_of_primitives(self) -> None:
        result = generate_ts_interfaces([1, 2, 3], "Numbers")
        assert "export type NumbersRecord = number;" in result
        assert "export type NumbersResponse = NumbersRecord[];" in result

    def test_array_of_strings(self) -> None:
        result = generate_ts_interfaces(["a", "b"], "Tags")
        assert "export type TagsRecord = string;" in result

    def test_nested_objects(self) -> None:
        sample = [{"id": 1, "address": {"city": "NYC", "zip": "10001"}}]
        result = generate_ts_interfaces(sample, "People")
        assert "export interface PeopleRecordAddress" in result
        assert "city: string;" in result
        assert "zip: string;" in result
        assert "address: PeopleRecordAddress;" in result

    def test_nested_array_field(self) -> None:
        sample = [{"tags": ["a", "b"]}]
        result = generate_ts_interfaces(sample, "Items")
        assert "tags: string[];" in result


# ---------------------------------------------------------------------------
# generate_ts_interfaces — dict responses (FLAPI multi-cube)
# ---------------------------------------------------------------------------


class TestGenerateTsInterfacesCubes:
    def test_multi_cube_response(self) -> None:
        sample = {
            "results": {
                "sales_cube": [{"id": 1, "amount": 100}],
                "customers_cube": [{"customer_id": "C1", "name": "Alice"}],
            }
        }
        result = generate_ts_interfaces(sample, "SalesPkg")
        # Per-cube interfaces
        assert "export interface SalesPkgSalesCube" in result
        assert "id: number;" in result
        assert "amount: number;" in result
        assert "export interface SalesPkgCustomersCube" in result
        assert "customer_id: string;" in result
        # Results wrapper
        assert "export interface SalesPkgResults" in result
        assert "sales_cube: SalesPkgSalesCube[];" in result
        assert "customers_cube: SalesPkgCustomersCube[];" in result
        # Top-level wrapper
        assert "export interface SalesPkgResponse" in result
        assert "results: SalesPkgResults;" in result

    def test_cube_with_empty_rows(self) -> None:
        sample = {"results": {"empty_cube": []}}
        result = generate_ts_interfaces(sample, "Test")
        assert "empty_cube: unknown[];" in result

    def test_single_cube(self) -> None:
        sample = {"results": {"orders": [{"id": 1, "total": 99.5}]}}
        result = generate_ts_interfaces(sample, "Order")
        assert "export interface OrderOrders" in result
        assert "total: number;" in result


# ---------------------------------------------------------------------------
# generate_ts_interfaces — dict responses (data-array wrapper)
# ---------------------------------------------------------------------------


class TestGenerateTsInterfacesDataWrapper:
    def test_data_key_wrapper(self) -> None:
        sample = {"data": [{"x": 1}], "total": 100}
        result = generate_ts_interfaces(sample, "Api")
        assert "export interface ApiRecord" in result
        assert "x: number;" in result
        assert "export interface ApiResponse" in result
        assert "data: ApiRecord[];" in result
        assert "total: number;" in result

    def test_items_key_wrapper(self) -> None:
        sample = {"items": [{"name": "foo"}], "page": 1}
        result = generate_ts_interfaces(sample, "Paged")
        assert "export interface PagedRecord" in result
        assert "items: PagedRecord[];" in result


# ---------------------------------------------------------------------------
# generate_ts_interfaces — other dict / primitive
# ---------------------------------------------------------------------------


class TestGenerateTsInterfacesOther:
    def test_plain_object(self) -> None:
        sample = {"name": "test", "count": 5}
        result = generate_ts_interfaces(sample, "Config")
        assert "export interface ConfigResponse" in result
        assert "name: string;" in result
        assert "count: number;" in result

    def test_empty_dict(self) -> None:
        result = generate_ts_interfaces({}, "Empty")
        assert "export interface EmptyResponse" in result
        assert "[key: string]: unknown;" in result

    def test_top_level_primitive_string(self) -> None:
        result = generate_ts_interfaces("hello", "Msg")
        assert "export type MsgResponse = string;" in result

    def test_top_level_primitive_number(self) -> None:
        result = generate_ts_interfaces(42, "Num")
        assert "export type NumResponse = number;" in result

    def test_top_level_none(self) -> None:
        result = generate_ts_interfaces(None, "Nil")
        assert "export type NilResponse = unknown;" in result

    def test_special_char_keys_are_quoted(self) -> None:
        sample = [{"full.name": "Alice", "ok": True}]
        result = generate_ts_interfaces(sample, "Dot")
        assert '"full.name": string;' in result
        assert "ok: boolean;" in result

    def test_empty_base_name_gets_default(self) -> None:
        result = generate_ts_interfaces({"x": 1}, "")
        assert "DataSourceResponse" in result

    def test_null_field_value(self) -> None:
        sample = [{"id": 1, "deleted_at": None}]
        result = generate_ts_interfaces(sample, "Row")
        assert "deleted_at: unknown;" in result

    def test_boolean_not_confused_with_number(self) -> None:
        """bool is a subclass of int in Python — ensure we emit 'boolean' not 'number'."""
        sample = [{"flag": True}]
        result = generate_ts_interfaces(sample, "Flags")
        assert "flag: boolean;" in result
