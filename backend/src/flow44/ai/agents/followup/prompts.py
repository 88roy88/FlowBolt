from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, Environment, FileSystemLoader

from flow44.ai.agents.execute.optional_packages import allowed_import_names, validate_optional_packages

_templates_dir = Path(__file__).parent / "templates"
_execute_templates_dir = Path(__file__).parents[1] / "execute" / "templates"
_env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML; autoescape would break them
    loader=ChoiceLoader([FileSystemLoader(str(_templates_dir)), FileSystemLoader(str(_execute_templates_dir))]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(template_name: str, **kwargs: Any) -> str:
    return _env.get_template(template_name).render(**kwargs)


def render_followup(*, project_summary: str, file_tree: str, selected_packages: list[str] | None = None) -> str:
    validated_packages = validate_optional_packages(selected_packages or [])
    return render(
        "followup.jinja2",
        project_summary=project_summary,
        file_tree=file_tree,
        allowed_imports=allowed_import_names(validated_packages),
    )
