from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, Environment, FileSystemLoader

from flow44.ai.generated_app_contract import generated_app_path_safety_prompt_context

_templates_dir = Path(__file__).parent / "templates"
_execute_templates_dir = Path(__file__).parents[1] / "execute" / "templates"
_env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML; autoescape would break them
    loader=ChoiceLoader([FileSystemLoader(str(_templates_dir)), FileSystemLoader(str(_execute_templates_dir))]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(template_name: str, **kwargs: Any) -> str:
    kwargs.setdefault("file_safety", generated_app_path_safety_prompt_context())
    return _env.get_template(template_name).render(**kwargs)


def render_followup(*, project_summary: str, file_tree: str) -> str:
    return render("followup.jinja2", project_summary=project_summary, file_tree=file_tree)
