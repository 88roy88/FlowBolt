from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, Environment, FileSystemLoader

from flow44.ai.generated_app_contract import generated_app_path_safety_prompt_context

_templates_dir = Path(__file__).parent / "templates"
_shared_templates_dir = Path(__file__).parents[1] / "templates"
_env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML; autoescape would break them
    loader=ChoiceLoader([FileSystemLoader(str(_templates_dir)), FileSystemLoader(str(_shared_templates_dir))]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(template_name: str, **kwargs: Any) -> str:
    kwargs.setdefault("file_safety", generated_app_path_safety_prompt_context())
    return _env.get_template(template_name).render(**kwargs)


def render_fix_errors(*, errors: str, files: dict[str, str]) -> str:
    return render("fix_errors.jinja2", errors=errors, files=files)


def render_fix_error_direct(
    *,
    error_message: str,
    error_file: str | None = None,
    error_line: int | None = None,
    error_stack: str | None = None,
    files: dict[str, str],
) -> str:
    return render(
        "fix_error_direct.jinja2",
        error_message=error_message,
        error_file=error_file,
        error_line=error_line,
        error_stack=error_stack,
        files=files,
    )
