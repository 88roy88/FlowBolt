import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from flow44.ai.agents.plan.prompts import render_data_source_analysis
from flow44.ai.codegen.data_source_module import generate_data_source_module
from flow44.ai.codegen.ts_types import sanitize_to_pascal_case
from flow44.ai.core.msg import user_msg
from flow44.ai.core.provider import complete_chat
from flow44.ai.helpers import parse_json_response
from flow44.db.project_data_source import DataSourceContext
from flow44.logic import data_source as ds_logic
from flow44.logic.models import DataSourceParamsInfo, DataSourceQuerySchema

logger = logging.getLogger(__name__)

_env = Environment(  # noqa: S701
    loader=FileSystemLoader(str(Path(__file__).parent.parent / "codegen" / "templates")),
    trim_blocks=True,
    lstrip_blocks=True,
)


async def fetch_and_analyze_data_source(
    data_source_id: str,
    user_content: str,
    authorization: str | None,
    model: str | None,
) -> DataSourceContext:
    ds_name, usage = await asyncio.gather(
        ds_logic.get_display_name(data_source_id, authorization=authorization),
        ds_logic.get_usage(data_source_id, authorization=authorization),
    )
    sanitized = sanitize_to_pascal_case(ds_name) or f"DataSource{data_source_id}"
    prompt = render_data_source_analysis(
        user_content=user_content,
        data_source_name=ds_name,
        sample_data=usage.sample,
        queries=[q.model_dump() for q in usage.queries],
        params_info=usage.params.model_dump(),
    )
    try:
        raw = await complete_chat(
            [user_msg("Analyze this data source.")],
            prompt,
            model_name=model,
        )
        analysis: dict[str, Any] = parse_json_response(raw)
    except Exception:
        logger.exception("Data source analysis failed, using degraded result")
        analysis = {
            "data_schema": "Unknown — analysis failed",
            "relevant_fields": "See raw data",
            "data_characteristics": ("Requires user input" if usage.sample is None else "Fetched from API"),
            "integration_notes": (
                f"Data preview: {json.dumps(usage.sample, indent=2)[:500]}"
                if usage.sample is not None
                else "No sample available — data source requires parameters."
            ),
        }
    return DataSourceContext(
        data_source_id=data_source_id,
        data_source_name=ds_name,
        sanitized_name=sanitized,
        queries=[q.model_dump() for q in usage.queries],
        params_info=usage.params.model_dump(),
        sample_data=usage.sample,
        can_run_without_input=usage.can_run,
        data_schema=analysis.get("data_schema", ""),
        relevant_fields=analysis.get("relevant_fields", ""),
        data_characteristics=analysis.get("data_characteristics", ""),
        integration_notes=analysis.get("integration_notes", ""),
        param_ux_hints=analysis.get("param_ux_hints", ""),
    )


def generate_data_source_files(ctx: DataSourceContext) -> dict[str, str]:
    sanitized = ctx.sanitized_name
    module_path = f"src/dataSources/{sanitized}.ts"
    docs_path = f"src/dataSources/{sanitized}.docs.md"
    params_info = DataSourceParamsInfo.model_validate(ctx.params_info)
    queries = [DataSourceQuerySchema.model_validate(q) for q in ctx.queries]
    content = generate_data_source_module(
        data_source_id=ctx.data_source_id,
        sanitized_name=ctx.sanitized_name,
        params_info=params_info,
        queries=queries,
    )
    docs = _generate_data_source_docs(ctx, params_info, queries)
    return {module_path: content, docs_path: docs}


_TYPE_PLACEHOLDERS = {bool: "<bool>", int: "<int>", float: "<number>"}


def _redact_sample_data(sample: dict[str, Any] | None) -> str | None:
    if sample is None:
        return None

    def _redact(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _redact(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_redact(obj[0])] if obj else []
        if obj is None:
            return None
        return _TYPE_PLACEHOLDERS.get(type(obj), "<string>")

    return json.dumps(_redact(sample), indent=2)


def _generate_data_source_docs(
    ctx: DataSourceContext,
    params_info: DataSourceParamsInfo,
    queries: list[DataSourceQuerySchema],
) -> str:
    return _env.get_template("data_source_docs.jinja2").render(
        ctx=ctx,
        params=params_info.parameters,
        queries=queries,
        redacted_sample=_redact_sample_data(ctx.sample_data),
    )
