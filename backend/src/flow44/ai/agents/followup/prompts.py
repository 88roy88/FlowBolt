from __future__ import annotations

from pathlib import Path
from typing import Literal

from jinja2 import ChoiceLoader, Environment, FileSystemLoader

from flow44.ai.generated_app_contract import (
    GeneratedAppPathSafetyPromptContext,
    generated_app_path_safety_prompt_context,
)

_templates_dir = Path(__file__).parent / "templates"
_shared_templates_dir = Path(__file__).parents[1] / "templates"
_env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML; autoescape would break them
    loader=ChoiceLoader([FileSystemLoader(str(_templates_dir)), FileSystemLoader(str(_shared_templates_dir))]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(
    template_name: Literal["followup.jinja2"],
    *,
    project_summary: str,
    file_tree: str,
    file_safety: GeneratedAppPathSafetyPromptContext,
) -> str:
    return _env.get_template(template_name).render(
        project_summary=project_summary,
        file_tree=file_tree,
        file_safety=file_safety,
    )


def render_followup(*, project_summary: str, file_tree: str) -> str:
    return render(
        "followup.jinja2",
        project_summary=project_summary,
        file_tree=file_tree,
        file_safety=generated_app_path_safety_prompt_context(),
    )
