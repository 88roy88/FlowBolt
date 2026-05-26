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


def package_has_react_router(files: dict[str, str]) -> bool:
    return "react-router-dom" in files.get("package.json", "")


def render_fix_errors(*, errors: str, files: dict[str, str], has_react_router: bool | None = None) -> str:
    if has_react_router is None:
        has_react_router = package_has_react_router(files)
    return render("fix_errors.jinja2", errors=errors, files=files, has_react_router=has_react_router)


def render_fix_error_direct(
    *,
    error_message: str,
    error_file: str | None = None,
    error_line: int | None = None,
    error_stack: str | None = None,
    files: dict[str, str],
    has_react_router: bool | None = None,
) -> str:
    if has_react_router is None:
        has_react_router = package_has_react_router(files)
    return render(
        "fix_error_direct.jinja2",
        error_message=error_message,
        error_file=error_file,
        error_line=error_line,
        error_stack=error_stack,
        files=files,
        has_react_router=has_react_router,
    )
