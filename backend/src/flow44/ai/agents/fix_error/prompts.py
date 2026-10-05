from __future__ import annotations

from pathlib import Path
from typing import Literal, overload

from jinja2 import ChoiceLoader, Environment, FileSystemLoader

from flow44.ai.agents.optional_packages import PackageRuleset, render_package_rules
from flow44.ai.agents.template_paths import TEMPLATE_PROMPTS_PATH
from flow44.ai.file_safety import (
    ProtectedFileRules,
    protected_file_rules,
)

_templates_dir = Path(__file__).parent / "templates"
_env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML; autoescape would break them
    loader=ChoiceLoader([FileSystemLoader(str(_templates_dir)), FileSystemLoader(str(TEMPLATE_PROMPTS_PATH))]),
    trim_blocks=True,
    lstrip_blocks=True,
)


@overload
def render(
    template_name: Literal["feedback.jinja2"],
    *,
    files: dict[str, str],
    package_rules: list[str] | None,
    file_safety: ProtectedFileRules,
) -> str: ...


@overload
def render(
    template_name: Literal["fix_error_direct.jinja2"],
    *,
    error_message: str,
    error_file: str | None,
    error_line: int | None,
    error_stack: str | None,
    files: dict[str, str],
    available_packages: list[str] | None,
    package_rules: list[str] | None,
    file_safety: ProtectedFileRules,
) -> str: ...


@overload
def render(template_name: str) -> str: ...


def render(template_name: str, **kwargs: object) -> str:
    return _env.get_template(template_name).render(**kwargs)


def render_feedback(*, files: dict[str, str], installed_packages: list[str] | None = None) -> str:
    return render(
        "feedback.jinja2",
        files=files,
        package_rules=render_package_rules(installed_packages or [], PackageRuleset.FIX_ERRORS) or None,
        file_safety=protected_file_rules(),
    )


def render_fix_error_direct(
    *,
    error_message: str,
    error_file: str | None = None,
    error_line: int | None = None,
    error_stack: str | None = None,
    files: dict[str, str],
    installed_packages: list[str] | None = None,
) -> str:
    return render(
        "fix_error_direct.jinja2",
        error_message=error_message,
        error_file=error_file,
        error_line=error_line,
        error_stack=error_stack,
        files=files,
        available_packages=installed_packages or None,
        package_rules=render_package_rules(installed_packages or [], PackageRuleset.FIX_ERRORS) or None,
        file_safety=protected_file_rules(),
    )
