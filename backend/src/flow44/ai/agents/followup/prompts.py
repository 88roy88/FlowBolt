from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_templates_dir = Path(__file__).parent / "templates"
_env = Environment(  # noqa: S701
    loader=FileSystemLoader(str(_templates_dir)), trim_blocks=True, lstrip_blocks=True
)


def render_followup(*, project_summary: str, file_tree: str) -> str:
    return _env.get_template("followup.jinja2").render(project_summary=project_summary, file_tree=file_tree)
