from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_templates_dir = Path(__file__).parent / "templates"
_env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML; autoescape would break them
    loader=FileSystemLoader(str(_templates_dir)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_enhance(
    *, is_new_project: bool, project_summary: str = "", data_source_names: list[str] | None = None
) -> str:
    template_name = "enhance_new.jinja2" if is_new_project else "enhance_followup.jinja2"
    return _env.get_template(template_name).render(
        project_summary=project_summary,
        data_source_names=data_source_names or [],
    )
