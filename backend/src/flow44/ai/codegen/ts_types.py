"""Deterministic JSON → TypeScript interface generator."""

from __future__ import annotations

import re
from typing import Any

from flow44.logic.models import DataSourceQuerySchema, FieldType

_MAX_DEPTH = 5

_FIELD_TYPE_TO_TS: dict[FieldType, str] = {
    "string": "string",
    "String": "string",
    "int": "number",
    "Int": "number",
    "Integer": "number",
    "double": "number",
    "float": "number",
    "Decimal": "number",
    "bool": "boolean",
    "Boolean": "boolean",
    "datetime": "string",
    "wkt": "string",
    "geojson": "string",
    "GeoEllipse": "string",
    "Haphoch": "string",
    "dynamic": "unknown",
    "Object": "Record<string, unknown>",
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
    sample_data: Any,
    base_name: str,
    *,
    queries: list[DataSourceQuerySchema] | None = None,
) -> str:
    """Generate TypeScript interfaces from a JSON sample.

    When `sample_data` is None (the data source needs user input and we
    couldn't run it), `queries` is used instead — each query becomes a
    cube under the FLAPI-shaped response wrapper.

    Returns a complete .ts file string with exported types.
    """
    if not base_name:
        base_name = "DataSource"

    if sample_data is None:
        if not queries:
            # Shouldn't happen: get_usage raises when metadata is empty.
            return f"export type {base_name}Response = unknown;\n"
        return _generate_from_schema(queries, base_name)

    interfaces: list[str] = []
    if isinstance(sample_data, list):
        _generate_from_list(sample_data, base_name, interfaces)
    elif isinstance(sample_data, dict):
        _generate_from_dict(sample_data, base_name, interfaces)
    else:
        ts = _infer_primitive(sample_data)
        interfaces.append(f"export type {base_name}Response = {ts};\n")

    return "\n".join(interfaces)


def _generate_from_schema(queries: list[DataSourceQuerySchema], base_name: str) -> str:
    """Build {Base}Response from FLAPI metadata when no sample is available.

    Shape mirrors the multi-cube wrapper: { results: { <cube>: Record[], ... } }.
    """
    interfaces: list[str] = []
    results_fields: list[str] = []
    for query in queries:
        type_name = f"{base_name}{sanitize_to_pascal_case(query.name)}"
        field_lines = [
            f"  {_quote_key(field.name)}: {_FIELD_TYPE_TO_TS.get(field.type, 'unknown')};" for field in query.fields
        ]
        body = "\n".join(field_lines) if field_lines else "  [key: string]: unknown;"
        interfaces.append(f"export interface {type_name} {{\n{body}\n}}\n")
        results_fields.append(f"  {_quote_key(query.name)}: {type_name}[];")
    results_body = "\n".join(results_fields)
    interfaces.append(f"\nexport interface {base_name}Results {{\n{results_body}\n}}\n")
    interfaces.append(
        f"\nexport interface {base_name}Response {{\n  results: {base_name}Results;\n}}\n"
    )
    return "\n".join(interfaces)


# ---------------------------------------------------------------------------
# Top-level shape handlers
# ---------------------------------------------------------------------------


def _generate_from_list(data: list[Any], base_name: str, interfaces: list[str]) -> None:
    """Handle top-level array response."""
    if not data:
        interfaces.append(
            f"// Sample data was an empty array — add fields as needed\n"
            f"export type {base_name}Record = unknown;\n\n"
            f"export type {base_name}Response = {base_name}Record[];\n"
        )
        return
    element = data[0]
    if isinstance(element, dict):
        _build_interface(element, f"{base_name}Record", interfaces, depth=0)
    else:
        interfaces.append(f"export type {base_name}Record = {_infer_primitive(element)};\n")
    interfaces.append(f"\nexport type {base_name}Response = {base_name}Record[];\n")


def _generate_from_dict(data: dict[str, Any], base_name: str, interfaces: list[str]) -> None:
    """Handle top-level dict response — detects cubes or data-array wrappers."""
    # FLAPI multi-cube: { results: { cube_name: rows[] } }
    cubes_key = _find_cubes_dict_key(data)
    if cubes_key is not None:
        _generate_cubes_wrapper(data, cubes_key, base_name, interfaces)
        return

    # Simple wrapper: { data: [...], meta: {...} }
    data_key = _find_data_array_key(data)
    if data_key is not None:
        _generate_array_wrapper(data, data_key, base_name, interfaces)
        return

    # Plain object
    _build_interface(data, f"{base_name}Response", interfaces, depth=0)


def _generate_cubes_wrapper(data: dict[str, Any], cubes_key: str, base_name: str, interfaces: list[str]) -> None:
    """Generate types for { results: { cube_name: rows[], ... } } pattern."""
    cubes = data[cubes_key]
    results_fields: list[str] = []
    for cube_name, rows in cubes.items():
        type_name = f"{base_name}{sanitize_to_pascal_case(cube_name)}"
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            _build_interface(rows[0], type_name, interfaces, depth=0)
            results_fields.append(f"  {_quote_key(cube_name)}: {type_name}[];")
        else:
            results_fields.append(f"  {_quote_key(cube_name)}: unknown[];")
    results_body = "\n".join(results_fields) if results_fields else "  [key: string]: unknown[];"
    interfaces.append(f"\nexport interface {base_name}Results {{\n{results_body}\n}}\n")

    wrapper_fields = _build_wrapper_fields(data, cubes_key, f"{base_name}Results", base_name, interfaces)
    interfaces.append(f"\nexport interface {base_name}Response {{\n" + "\n".join(wrapper_fields) + "\n}\n")


def _generate_array_wrapper(data: dict[str, Any], data_key: str, base_name: str, interfaces: list[str]) -> None:
    """Generate types for { data: [...], meta: {...} } pattern."""
    arr = data[data_key]
    if arr and isinstance(arr[0], dict):
        _build_interface(arr[0], f"{base_name}Record", interfaces, depth=0)
    else:
        ts = _infer_primitive(arr[0]) if arr else "unknown"
        interfaces.append(f"export type {base_name}Record = {ts};\n")

    wrapper_fields = _build_wrapper_fields(data, data_key, f"{base_name}Record[]", base_name, interfaces)
    interfaces.append(f"\nexport interface {base_name}Response {{\n" + "\n".join(wrapper_fields) + "\n}\n")


def _build_wrapper_fields(
    data: dict[str, Any],
    special_key: str,
    special_type: str,
    base_name: str,
    interfaces: list[str],
) -> list[str]:
    """Build field lines for a wrapper interface, substituting *special_key*."""
    fields: list[str] = []
    for key, val in data.items():
        if key == special_key:
            fields.append(f"  {_quote_key(key)}: {special_type};")
        else:
            ts_type = _infer_type(val, f"{base_name}{_capitalize(key)}", interfaces, depth=1)
            fields.append(f"  {_quote_key(key)}: {ts_type};")
    return fields


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_interface(obj: dict[str, Any], name: str, interfaces: list[str], *, depth: int) -> None:
    """Build a named interface from a dict and append to *interfaces*."""
    fields: list[str] = []
    for key, val in obj.items():
        child_name = f"{name}{_capitalize(key)}"
        ts_type = _infer_type(val, child_name, interfaces, depth=depth + 1)
        fields.append(f"  {_quote_key(key)}: {ts_type};")
    body = "\n".join(fields) if fields else "  [key: string]: unknown;"
    interfaces.append(f"export interface {name} {{\n{body}\n}}\n")


def _infer_type(value: Any, child_name: str, interfaces: list[str], *, depth: int) -> str:  # noqa: PLR0911
    """Return a TS type string for *value*, potentially creating sub-interfaces."""
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return _infer_list_type(value, child_name, interfaces, depth=depth)
    if isinstance(value, dict):
        if depth < _MAX_DEPTH:
            _build_interface(value, child_name, interfaces, depth=depth)
            return child_name
        return "Record<string, unknown>"
    return "unknown"


def _infer_list_type(value: list[Any], child_name: str, interfaces: list[str], *, depth: int) -> str:
    """Infer TypeScript type for a list value."""
    if not value:
        return "unknown[]"
    elem = value[0]
    if isinstance(elem, dict):
        if depth < _MAX_DEPTH:
            _build_interface(elem, child_name, interfaces, depth=depth)
            return f"{child_name}[]"
        return "Record<string, unknown>[]"
    return f"{_infer_primitive(elem)}[]"


def _infer_primitive(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return "unknown"


def _find_cubes_dict_key(obj: dict[str, Any]) -> str | None:
    """Detect FLAPI multi-cube pattern: { results: { cube: rows[], ... } }.

    Returns the key name if found, else None.
    """
    for candidate in ("results", "data", "cubes", "queries"):
        val = obj.get(candidate)
        if isinstance(val, dict) and val and all(isinstance(v, list) for v in val.values()):
            return candidate
    return None


def _find_data_array_key(obj: dict[str, Any]) -> str | None:
    """Detect a wrapper object with a primary data array.

    Looks for a key named 'data', 'results', 'items', 'records', or 'rows'
    whose value is a non-empty list.
    """
    for candidate in ("data", "results", "items", "records", "rows"):
        val = obj.get(candidate)
        if isinstance(val, list) and val:
            return candidate
    return None


def _capitalize(s: str) -> str:
    return s[:1].upper() + s[1:] if s else ""


def _quote_key(key: str) -> str:
    """Quote keys that aren't valid JS identifiers."""
    if _IDENT_RE.match(key):
        return key
    escaped = key.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
