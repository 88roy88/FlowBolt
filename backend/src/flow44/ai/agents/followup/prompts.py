from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

_templates_dir = Path(__file__).parent / "templates"
_env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML; autoescape would break them
    loader=FileSystemLoader(str(_templates_dir)), trim_blocks=True, lstrip_blocks=True
)


def render(template_name: str, **kwargs: Any) -> str:
    return _env.get_template(template_name).render(**kwargs)


def render_followup(*, project_summary: str, file_tree: str) -> str:
    return render("followup.jinja2", project_summary=project_summary, file_tree=file_tree)
