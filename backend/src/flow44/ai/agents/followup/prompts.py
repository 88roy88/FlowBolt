from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

_templates_dir = Path(__file__).parent / "templates"
_env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML; autoescape would break them
    loader=FileSystemLoader(str(_templates_dir)), trim_blocks=True, lstrip_blocks=True
)

_SAMPLE_DATA_MAX_CHARS = 800


def render(template_name: str, **kwargs: Any) -> str:
    return _env.get_template(template_name).render(**kwargs)


def render_followup(
    *,
    project_summary: str,
    file_tree: str,
    data_source_contexts: list[dict[str, Any]] | None = None,
) -> str:
    prepared_ds: list[dict[str, Any]] | None = None
    if data_source_contexts:
        prepared_ds = []
        for ctx in data_source_contexts:
            entry = {**ctx}
            sample = ctx.get("sample_data")
            entry["sample_data_json"] = (
                json.dumps(sample, indent=2)[:_SAMPLE_DATA_MAX_CHARS] if sample is not None else None
            )
            prepared_ds.append(entry)

    return render(
        "followup.jinja2",
        project_summary=project_summary,
        file_tree=file_tree,
        data_source_contexts=prepared_ds,
    )
