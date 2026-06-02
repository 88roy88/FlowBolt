"""Deterministic JSON → TypeScript interface generator."""

from __future__ import annotations

import re

from flow44.logic.models import DataSourceQuerySchema, FieldType

_FIELD_TYPE_TO_TS: dict[FieldType, str] = {
    "string": "string",
    "int": "number",
    "double": "number",
    "bool": "boolean",
    "datetime": "Date",
    "wkt": "string",
}

# Keys that look like identifiers don't need quoting
_IDENT_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def sanitize_to_pascal_case(name: str) -> str:
    """Convert a display name to PascalCase for use in TypeScript identifiers.

    >>> sanitize_to_pascal_case("Weather Forecast API")
    'WeatherForecastApi'
    >>> sanitize_to_pascal_case("my-data_source 2")
    'MyDataSource2'
    """
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", name).strip()
    if not cleaned:
        return ""
    parts = cleaned.split()
    return "".join(p[0].upper() + p[1:] if p else "" for p in parts)


def generate_ts_interfaces(
    base_name: str,
    *,
    queries: list[DataSourceQuerySchema] | None = None,
) -> str:
    """Generate TypeScript interfaces from FLAPI query schema."""
    if not base_name:
        base_name = "DataSource"

    if not queries:
        return f"export type {base_name}Response = unknown;\n"

    return _generate_from_schema(queries, base_name)


def _generate_from_schema(queries: list[DataSourceQuerySchema], base_name: str) -> str:
    """Build typed interfaces from FLAPI metadata."""
    interfaces: list[str] = []
    results_fields: list[str] = []
    for query in queries:
        type_name = f"{base_name}{sanitize_to_pascal_case(query.name)}"
        field_lines = [
            f"  {_quote_key(field.name)}: {_FIELD_TYPE_TO_TS[field.type]}; // {field.display_name}" for field in query.fields
        ]
        body = "\n".join(field_lines) if field_lines else "  [key: string]: unknown;"
        interfaces.append(f"// {query.display_name}\nexport interface {type_name} {{\n{body}\n}}\n")
        results_fields.append(f"  {_quote_key(query.name)}: {type_name}[];")
    results_body = "\n".join(results_fields)
    interfaces.append(f"export interface {base_name}Results {{\n{results_body}\n}}\n")
    return "\n".join(interfaces)


def _quote_key(key: str) -> str:
    """Quote keys that aren't valid JS identifiers."""
    if _IDENT_RE.match(key):
        return key
    escaped = key.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
