from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, TemplateNotFound

from flow44.ai.agents.execute.optional_packages import OPTIONAL_PACKAGES, OptionalPackagePrompt

_templates_dir = Path(__file__).parent / "templates"
_execute_templates_dir = Path(__file__).parents[1] / "execute" / "templates"
_env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML; autoescape would break them
    loader=ChoiceLoader([FileSystemLoader(str(_templates_dir)), FileSystemLoader(str(_execute_templates_dir))]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(template_name: str, **kwargs: Any) -> str:
    return _env.get_template(template_name).render(**kwargs)


def render_fix_errors(*, errors: str, files: dict[str, str]) -> str:
    return render("fix_errors.jinja2", errors=errors, files=files, package_fix_rules=_package_fix_rules(files))


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
        package_fix_rules=_package_fix_rules(files),
    )


def _package_fix_rules(files: dict[str, str]) -> list[str]:
    package_json = files.get("package.json", "")
    blocks: list[str] = []
    for name, package in OPTIONAL_PACKAGES.items():
        if name not in package_json:
            continue
        try:
            blocks.append(render(package.prompt_template(OptionalPackagePrompt.FIX_ERRORS_RULES)).strip())
        except TemplateNotFound:
            continue
    return blocks
