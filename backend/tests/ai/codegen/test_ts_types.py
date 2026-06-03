"""Tests for flow44.ai.codegen.ts_types."""

from __future__ import annotations

from flow44.ai.codegen.ts_types import (
    generate_ts_interfaces,
    sanitize_to_pascal_case,
)
from flow44.logic.models import DataSourceFieldSchema, DataSourceQuerySchema

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
# generate_ts_interfaces — schema-based
# ---------------------------------------------------------------------------


class TestGenerateTsInterfacesSchemaOnly:
    def test_single_query_produces_cube_and_results(self) -> None:
        queries = [
            DataSourceQuerySchema(
                name="sales",
                display_name="Sales",
                description="Sales rows",
                fields=[
                    DataSourceFieldSchema(name="id", display_name="ID", type="int"),
                    DataSourceFieldSchema(name="amount", display_name="Amount", type="double"),
                    DataSourceFieldSchema(name="active", display_name="Active", type="bool"),
                    DataSourceFieldSchema(name="created", display_name="Created", type="datetime"),
                ],
            )
        ]
        result = generate_ts_interfaces("Report", queries=queries)
        assert "export interface ReportSales" in result
        assert "id: number;" in result
        assert "amount: number;" in result
        assert "active: boolean;" in result
        assert "created: Date;" in result
        assert "export interface ReportResults" in result
        assert "Sales: ReportSales[];" in result

    def test_multi_query_produces_multiple_cubes(self) -> None:
        queries = [
            DataSourceQuerySchema(
                name="orders",
                display_name="Orders",
                description="",
                fields=[DataSourceFieldSchema(name="id", display_name="ID", type="int")],
            ),
            DataSourceQuerySchema(
                name="customers",
                display_name="Customers",
                description="",
                fields=[DataSourceFieldSchema(name="name", display_name="Name", type="string")],
            ),
        ]
        result = generate_ts_interfaces("Multi", queries=queries)
        assert "export interface MultiOrders" in result
        assert "export interface MultiCustomers" in result
        assert "Orders: MultiOrders[];" in result
        assert "Customers: MultiCustomers[];" in result

    def test_no_queries_falls_back_to_unknown(self) -> None:
        result = generate_ts_interfaces("X")
        assert "export type XResponse = unknown;" in result

    def test_empty_base_name_gets_default(self) -> None:
        result = generate_ts_interfaces("")
        assert "DataSource" in result

    def test_special_char_keys_are_quoted(self) -> None:
        queries = [
            DataSourceQuerySchema(
                name="my-cube",
                display_name="My cube",
                description="",
                fields=[DataSourceFieldSchema(name="full.name", display_name="Name", type="string")],
            )
        ]
        result = generate_ts_interfaces("Dot", queries=queries)
        assert '"full.name": string;' in result
