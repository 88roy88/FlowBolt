"""Deterministic generator for a data-source API module (TS).

Emits a single file per data source at ``src/dataSources/{Sanitized}.ts``
containing both the response type and an async function that calls the
FLAPI run endpoint. The function's signature uses a named-parameters object
where every param is typed as ``FlowParamValue``.
"""

from __future__ import annotations

import re
from typing import Any, assert_never

from flow44.ai.codegen.ts_types import generate_ts_interfaces
from flow44.logic.models import DataSourceParamsInfo, DataSourceQuerySchema, ParamDefinition, ParamType

_TYPE_DEFS: dict[str, str] = {
    "datetime": "type DateRange = { From: Date; To: Date };",
    "geographic": "type WKT = string;",
}

# Param names that would clip a JS/TS reserved word when used as a parameter
# or property identifier. A trailing underscore is appended to avoid the clash
# without mangling the body key (which stays the original FLAPI name).
_TS_RESERVED: frozenset[str] = frozenset(
    {
        "break", "case", "catch", "class", "const", "continue", "debugger",
        "default", "delete", "do", "else", "enum", "export", "extends", "false",
        "finally", "for", "function", "if", "import", "in", "instanceof", "new",
        "null", "return", "super", "switch", "this", "throw", "true", "try",
        "typeof", "var", "void", "while", "with", "yield",
        # Strict-mode / contextual that still trip TS in param position:
        "let", "static", "implements", "interface", "package", "private",
        "protected", "public", "await", "async", "from", "as", "of",
    }
)


def generate_data_source_module(  # noqa: PLR0913
    *,
    data_source_id: str,
    sanitized_name: str,
    params_info: DataSourceParamsInfo,
    sample_data: Any,
    queries: list[DataSourceQuerySchema] | None = None,
) -> str:
    """Build the full .ts content for a data source."""
    response_type = f"{sanitized_name}Response"
    results_type = f"{sanitized_name}Results"
    types_block = generate_ts_interfaces(sample_data, sanitized_name, queries=queries).rstrip()

    function_name = _function_name(sanitized_name)
    required = [p for p in params_info.parameters if p.is_required or p.is_require_any]
    optional = [p for p in params_info.parameters if not (p.is_required or p.is_require_any)]

    signature = _build_signature(function_name, required, optional, results_type)
    body = _build_body(data_source_id, required, optional, response_type)

    used_types = {p.type for p in params_info.parameters}
    type_defs = "\n".join(v for k, v in _TYPE_DEFS.items() if k in used_types)

    parts = ["import { fetchWithAuth } from '../api/client';"]
    if type_defs:
        parts.append(type_defs)
    parts.append(types_block)
    parts.append(f"{signature} {{\n{body}}}")
    return "\n\n".join(parts) + "\n"


def _function_name(sanitized_name: str) -> str:
    return "dataSource" + sanitized_name


def _param_type_to_ts(param_type: ParamType) -> str:
    match param_type:
        case "int" | "double":
            return "number"
        case "string":
            return "string" 
        case "bool":
            return "boolean"
        case "datetime":
            return "DateRange"
        case "timestamp":
            return "Date"
        case "geographic":
            return "WKT"
        case _ as unreachable:
            assert_never(unreachable)


def _unique_idents(params: list[ParamDefinition]) -> dict[int, str]:
    """Return a TS identifier for each param, prefixing with camelCase cube_id on collision."""
    base = {id(p): _ts_ident(p.name) for p in params}
    counts: dict[str, int] = {}
    for ident in base.values():
        counts[ident] = counts.get(ident, 0) + 1
    result: dict[int, str] = {}
    for p in params:
        ident = base[id(p)]
        if counts[ident] > 1:
            ident = _ts_ident(p.cube_id) + "_" + ident
        result[id(p)] = ident
    return result


def _build_signature(
    function_name: str,
    required: list[ParamDefinition],
    optional: list[ParamDefinition],
    response_type: str,
) -> str:
    all_params = required + optional
    if not all_params:
        return f"export async function {function_name}(): Promise<{response_type}>"

    idents = _unique_idents(all_params)
    param_names = ", ".join(idents[id(p)] for p in all_params)
    fields: list[str] = []
    for p in required:
        fields.append(f"{idents[id(p)]}: {_param_type_to_ts(p.type)}")
    for p in optional:
        fields.append(f"{idents[id(p)]}?: {_param_type_to_ts(p.type)}")
    type_body = "; ".join(fields)

    return f"export async function {function_name}({{ {param_names} }}: {{ {type_body} }}): Promise<{response_type}>"


def _build_body(
    data_source_id: str,
    required: list[ParamDefinition],
    optional: list[ParamDefinition],
    response_type: str,
) -> str:
    lines: list[str] = []
    path = f"/api/data-source/{data_source_id}/run"

    if not required and not optional:
        lines.append(f"  const res = await fetchWithAuth('{path}');\n")
    else:
        all_params = required + optional
        idents = _unique_idents(all_params)
        cube_ids = sorted({p.cube_id for p in all_params})
        lines.append("  const body: Record<string, Record<string, unknown>> = {};\n")
        for cube_id in cube_ids:
            lines.append(f"  body[{_js_string(cube_id)}] = {{}};\n")
        for p in required:
            lines.append(
                f"  body[{_js_string(p.cube_id)}][{_js_string(p.name)}] = {idents[id(p)]};\n"
            )
        for p in optional:
            ident = idents[id(p)]
            lines.append(
                f"  if ({ident} !== undefined) body[{_js_string(p.cube_id)}][{_js_string(p.name)}] = {ident};\n"
            )
        lines.append(f"  const res = await fetchWithAuth('{path}', body);\n")

    lines.append(f"  const envelope = (await res.json()) as {response_type};\n")
    lines.append("  return envelope.data;\n")
    return "".join(lines)


def _ts_ident(name: str) -> str:
    """Turn a FLAPI param name into a safe TS identifier.

    Snake-case is camel-cased; reserved words get a trailing underscore so the
    emitted signature stays valid TS. The FLAPI wire name used for the body
    key is handled separately and always uses the original string.
    """
    parts = re.split(r"_+", name)
    head, *rest = parts
    ident = head + "".join(p[:1].upper() + p[1:] for p in rest if p)
    if ident in _TS_RESERVED:
        return f"{ident}_"
    return ident


def _js_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"
