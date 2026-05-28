"""Deterministic generator for a data-source API module (TS).

Emits a single file per data source at ``src/dataSources/{Sanitized}.ts``
containing both the response type and an async function that calls the
FLAPI run endpoint. The function's signature uses a named-parameters object
where every param is typed as ``FlowParamValue``.
"""

from __future__ import annotations

import re
from typing import Any

from flow44.ai.codegen.ts_types import generate_ts_interfaces
from flow44.logic.models import DataSourceParamsInfo, DataSourceQuerySchema, ParamDefinition

_FLOW_PARAM_VALUE_TYPE_DEF = """\
type TextValue = { Name: string; Value: string }[];
type DateRangeValue = { From: string; To: string };

type FlowParamValue = TextValue | DateRangeValue;"""

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
    types_block = generate_ts_interfaces(sample_data, sanitized_name, queries=queries).rstrip()

    function_name = _function_name(sanitized_name)
    required = [p for p in params_info.parameters if p.is_required or p.is_require_any]
    optional = [p for p in params_info.parameters if not (p.is_required or p.is_require_any)]

    signature = _build_signature(function_name, required, optional, response_type)
    body = _build_body(data_source_id, required, optional, response_type)

    return (
        "import { fetchWithAuth } from '../api/client';\n\n"
        f"{_FLOW_PARAM_VALUE_TYPE_DEF}\n\n"
        f"{types_block}\n\n"
        f"{signature} {{\n{body}}}\n"
    )


def _function_name(sanitized_name: str) -> str:
    return "dataSource" + sanitized_name


def _build_signature(
    function_name: str,
    required: list[ParamDefinition],
    optional: list[ParamDefinition],
    response_type: str,
) -> str:
    all_params = required + optional
    if not all_params:
        return f"export async function {function_name}(): Promise<{response_type}>"

    param_names = ", ".join(_ts_ident(p.name) for p in all_params)
    fields: list[str] = []
    for p in required:
        fields.append(f"{_ts_ident(p.name)}: FlowParamValue")
    for p in optional:
        fields.append(f"{_ts_ident(p.name)}?: FlowParamValue")
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
        cube_ids = sorted({p.cube_id for p in all_params})
        lines.append("  const body: Record<string, Record<string, unknown>> = {};\n")
        for cube_id in cube_ids:
            lines.append(f"  body[{_js_string(cube_id)}] = {{}};\n")
        for p in required:
            lines.append(
                f"  body[{_js_string(p.cube_id)}][{_js_string(p.name)}] = {_ts_ident(p.name)};\n"
            )
        for p in optional:
            ident = _ts_ident(p.name)
            lines.append(
                f"  if ({ident} !== undefined) body[{_js_string(p.cube_id)}][{_js_string(p.name)}] = {ident};\n"
            )
        lines.append(f"  const res = await fetchWithAuth('{path}', body);\n")

    lines.append(f"  const envelope = (await res.json()) as {{ data: {response_type} }};\n")
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
