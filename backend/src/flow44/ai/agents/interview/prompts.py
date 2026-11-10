from __future__ import annotations

from pathlib import Path

from jinja2 import ChoiceLoader, Environment, FileSystemLoader

from flow44.ai.agents.template_paths import TEMPLATE_PROMPTS_PATH
from flow44.db.project_data_source import DataSourceContext

_templates_dir = Path(__file__).parent / "templates"
_env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML; autoescape would break them
    loader=ChoiceLoader([FileSystemLoader(str(_templates_dir)), FileSystemLoader(str(TEMPLATE_PROMPTS_PATH))]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_interview(*, data_source_contexts: list[DataSourceContext] | None = None) -> str:
    prepared = [ctx.to_prompt_context() for ctx in data_source_contexts] if data_source_contexts else None
    return _env.get_template("interview.jinja2").render(data_source_contexts=prepared)
