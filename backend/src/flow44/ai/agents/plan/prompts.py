from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

_templates_dir = Path(__file__).parent / "templates"
_env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML; autoescape would break them
    loader=FileSystemLoader(str(_templates_dir)), trim_blocks=True, lstrip_blocks=True
)


def render(template_name: str, **kwargs: Any) -> str:
    return _env.get_template(template_name).render(**kwargs)


def render_architecture(*, data_source_contexts: list[dict[str, Any]] | None = None) -> str:
    prepared = None
    if data_source_contexts:
        prepared = [
            {**ctx, "sample_data_json": json.dumps(ctx.get("sample_data", {}), indent=2)[:1000]}
            for ctx in data_source_contexts
        ]
    return render("architecture.jinja2", data_source_contexts=prepared)


def render_ux_design() -> str:
    return render("ux_design.jinja2")


def render_user_plan(*, has_feedback: bool = False) -> str:
    return render("user_plan.jinja2", has_feedback=has_feedback)


def render_data_source_analysis(*, user_content: str, data_source_name: str, sample_data: Any) -> str:
    sample_json = json.dumps(sample_data, indent=2)[:2000] if sample_data else "{}"
    return render(
        "data_source_analysis.jinja2",
        user_content=user_content,
        data_source_name=data_source_name,
        sample_data_json=sample_json,
    )


# Constants
UX_DESIGN_PROMPT = render_ux_design()
