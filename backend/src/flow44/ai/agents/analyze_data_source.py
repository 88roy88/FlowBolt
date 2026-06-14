import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from flow44.ai.agents.plan.prompts import render_data_source_analysis
from flow44.ai.codegen.data_source_module import generate_data_source_module
from flow44.ai.codegen.ts_types import sanitize_to_pascal_case
from flow44.ai.core.messages import Message
from flow44.ai.core.provider import complete_chat
from flow44.ai.helpers import parse_json_response
from flow44.db.project_data_source import DataSourceContext
from flow44.logic import data_source as ds_logic
from flow44.logic.models import DataSourceParamsInfo, DataSourceQuerySchema

logger = logging.getLogger(__name__)


async def fetch_and_analyze_data_source(
    data_source_id: str,
    user_content: str,
    authorization: str | None,
    model: str | None,
    llm_metadata_fn: Callable[[str], dict[str, Any]],
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
            [Message.user("Analyze this data source.")],
            prompt,
            model=model,
            metadata=llm_metadata_fn("data_source_analysis"),
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
    module_path = f"src/dataSources/{ctx.sanitized_name}.ts"
    params_info = DataSourceParamsInfo.model_validate(ctx.params_info)
    queries = [DataSourceQuerySchema.model_validate(q) for q in ctx.queries]
    content = generate_data_source_module(
        data_source_id=ctx.data_source_id,
        sanitized_name=ctx.sanitized_name,
        params_info=params_info,
        queries=queries,
    )
    return {module_path: content}
