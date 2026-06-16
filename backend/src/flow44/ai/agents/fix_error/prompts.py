from __future__ import annotations

from pathlib import Path
from typing import Literal, overload

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, TemplateNotFound

from flow44.ai.agents.execute.optional_packages import (
    OPTIONAL_PACKAGES,
    OptionalPackagePrompt,
    allowed_import_names,
    validate_optional_packages,
)
from flow44.ai.agents.template_paths import TEMPLATE_PROMPTS_PATH
from flow44.ai.generated_app_contract import (
    GeneratedAppPathSafetyPromptContext,
    generated_app_path_safety_prompt_context,
)

_templates_dir = Path(__file__).parent / "templates"
_env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML; autoescape would break them
    loader=ChoiceLoader([FileSystemLoader(str(_templates_dir)), FileSystemLoader(str(TEMPLATE_PROMPTS_PATH))]),
    trim_blocks=True,
    lstrip_blocks=True,
)


@overload
def render(
    template_name: Literal["fix_errors.jinja2"],
    *,
    errors: str,
    files: dict[str, str],
    allowed_imports: list[str],
    package_fix_rules: list[str],
    package_unselected_fix_rules: list[str],
    file_safety: GeneratedAppPathSafetyPromptContext,
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
    allowed_imports: list[str],
    package_fix_rules: list[str],
    package_unselected_fix_rules: list[str],
    file_safety: GeneratedAppPathSafetyPromptContext,
) -> str: ...


@overload
def render(template_name: str) -> str: ...


def render(template_name: str, **kwargs: object) -> str:
    return _env.get_template(template_name).render(**kwargs)


def render_fix_errors(*, errors: str, files: dict[str, str], selected_packages: list[str] | None = None) -> str:
    validated_packages = validate_optional_packages(selected_packages or [])
    return render(
        "fix_errors.jinja2",
        errors=errors,
        files=files,
        allowed_imports=allowed_import_names(validated_packages),
        package_fix_rules=_package_fix_rules(validated_packages),
        package_unselected_fix_rules=_package_unselected_fix_rules(validated_packages),
        file_safety=generated_app_path_safety_prompt_context(),
    )


def render_fix_error_direct(
    *,
    error_message: str,
    error_file: str | None = None,
    error_line: int | None = None,
    error_stack: str | None = None,
    files: dict[str, str],
    selected_packages: list[str] | None = None,
) -> str:
    validated_packages = validate_optional_packages(selected_packages or [])
    return render(
        "fix_error_direct.jinja2",
        error_message=error_message,
        error_file=error_file,
        error_line=error_line,
        error_stack=error_stack,
        files=files,
        allowed_imports=allowed_import_names(validated_packages),
        package_fix_rules=_package_fix_rules(validated_packages),
        package_unselected_fix_rules=_package_unselected_fix_rules(validated_packages),
        file_safety=generated_app_path_safety_prompt_context(),
    )


def _package_fix_rules(selected_packages: list[str]) -> list[str]:
    blocks: list[str] = []
    for name in selected_packages:
        package = OPTIONAL_PACKAGES[name]
        try:
            blocks.append(render(package.prompt_template(OptionalPackagePrompt.FIX_ERRORS_RULES)).strip())
        except TemplateNotFound:
            continue
    return blocks


def _package_unselected_fix_rules(selected_packages: list[str]) -> list[str]:
    selected = set(selected_packages)
    blocks: list[str] = []
    for name, package in OPTIONAL_PACKAGES.items():
        if name in selected:
            continue
        try:
            blocks.append(render(package.prompt_template(OptionalPackagePrompt.FIX_ERRORS_UNSELECTED_RULES)).strip())
        except TemplateNotFound:
            continue
    return blocks
