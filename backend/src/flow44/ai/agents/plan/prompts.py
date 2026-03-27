from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

_templates_dir = Path(__file__).parent / "templates"
_env = Environment(  # noqa: S701
    loader=FileSystemLoader(str(_templates_dir)), trim_blocks=True, lstrip_blocks=True
)


def render_classify() -> str:
    return _env.get_template("classify.jinja2").render()


def render_architecture(*, data_source_contexts: list[dict[str, Any]] | None = None) -> str:
    prepared = None
    if data_source_contexts:
        prepared = [
            {**ctx, "sample_data_json": json.dumps(ctx.get("sample_data", {}), indent=2)[:1000]}
            for ctx in data_source_contexts
        ]
    return _env.get_template("architecture.jinja2").render(data_source_contexts=prepared)


def render_ux_design() -> str:
    return _env.get_template("ux_design.jinja2").render()


def render_user_plan(*, has_feedback: bool = False) -> str:
    return _env.get_template("user_plan.jinja2").render(has_feedback=has_feedback)


def render_data_source_analysis(
    *,
    user_content: str,
    data_source_name: str,
    sample_data: Any,
) -> str:
    return _env.get_template("data_source_analysis.jinja2").render(
        user_content=user_content,
        data_source_name=data_source_name,
        sample_data_json=json.dumps(sample_data, indent=2)[:2000],
    )


# Pre-rendered constants
UX_DESIGN_PROMPT = render_ux_design()
USER_PLAN_PROMPT = render_user_plan()
