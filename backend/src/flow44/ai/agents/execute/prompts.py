from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal, overload

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, TemplateNotFound

from flow44.ai.agents.execute.optional_packages import (
    OPTIONAL_PACKAGES,
    OptionalPackagePrompt,
    allowed_import_names,
    optional_package_prompt_context,
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
    template_name: Literal["merge.jinja2"],
    *,
    has_data_sources: bool,
    package_merge_rules: list[str],
    package_unselected_merge_rules: list[str],
    file_safety: GeneratedAppPathSafetyPromptContext,
) -> str: ...


@overload
def render(template_name: Literal["package_decision.jinja2"], *, optional_packages: list[dict[str, str]]) -> str: ...


@overload
def render(template_name: Literal["summary.jinja2"]) -> str: ...


@overload
def render(
    template_name: Literal["codegen.jinja2"],
    *,
    task_title: str,
    task_description: str,
    task_files: list[str],
    architecture_json: str,
    ux_json: str,
    dependency_files: dict[str, str] | None,
    other_completed_exports: dict[str, str] | None,
    data_source_contexts: list[dict[str, Any]] | None,
    allowed_imports: list[str],
    package_contexts: list[str],
    package_rules: list[str],
    package_unselected_rules: list[str],
    file_safety: GeneratedAppPathSafetyPromptContext,
) -> str: ...


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
def render(template_name: str) -> str: ...


def render(template_name: str, **kwargs: object) -> str:
    return _env.get_template(template_name).render(**kwargs)


def render_merge(*, has_data_sources: bool = False, selected_packages: list[str] | None = None) -> str:
    validated_packages = validate_optional_packages(selected_packages or [])
    return render(
        "merge.jinja2",
        has_data_sources=has_data_sources,
        package_merge_rules=_render_optional_package_prompts(validated_packages, OptionalPackagePrompt.MERGE_RULES),
        package_unselected_merge_rules=_render_unselected_optional_package_prompts(
            validated_packages, OptionalPackagePrompt.MERGE_UNSELECTED_RULES
        ),
        file_safety=generated_app_path_safety_prompt_context(),
    )


def render_package_decision() -> str:
    return render("package_decision.jinja2", optional_packages=optional_package_prompt_context())


def render_summary() -> str:
    return render("summary.jinja2")


def render_codegen(  # noqa: PLR0913
    *,
    task_title: str,
    task_description: str,
    task_files: list[str],
    architecture: dict[str, Any],
    ux_design: dict[str, Any],
    dependency_files: dict[str, str] | None = None,
    other_completed_files: dict[str, str] | None = None,
    data_source_contexts: list[dict[str, Any]] | None = None,
    selected_packages: list[str] | None = None,
) -> str:
    prepared_sources = None
    if data_source_contexts:
        prepared_sources = [
            {
                **ctx,
                "sample_data_json": (
                    json.dumps(ctx["sample_data"], indent=2)[:1000] if ctx.get("sample_data") is not None else None
                ),
            }
            for ctx in data_source_contexts
        ]

    other_exports = None
    if other_completed_files:
        other_exports = {}
        for path, content in other_completed_files.items():
            exports = _extract_exports(content)
            if exports:
                other_exports[path] = exports
            else:
                lines = content.split("\n")
                preview = "\n".join(lines[:50])
                if len(lines) > 50:
                    preview += f"\n... ({len(lines) - 50} more lines)"
                other_exports[path] = preview

    validated_packages = validate_optional_packages(selected_packages or [])
    return render(
        "codegen.jinja2",
        task_title=task_title,
        task_description=task_description,
        task_files=task_files,
        architecture_json=json.dumps(architecture, indent=2, ensure_ascii=False),
        ux_json=json.dumps(ux_design, indent=2, ensure_ascii=False),
        dependency_files=dependency_files,
        other_completed_exports=other_exports,
        data_source_contexts=prepared_sources,
        allowed_imports=allowed_import_names(validated_packages),
        package_contexts=_render_optional_package_prompts(validated_packages, OptionalPackagePrompt.CODEGEN_CONTEXT),
        package_rules=_render_optional_package_prompts(validated_packages, OptionalPackagePrompt.CODEGEN_RULES),
        package_unselected_rules=_render_unselected_optional_package_prompts(
            validated_packages, OptionalPackagePrompt.CODEGEN_UNSELECTED_RULES
        ),
        file_safety=generated_app_path_safety_prompt_context(),
    )


def render_fix_errors(*, errors: str, files: dict[str, str], selected_packages: list[str] | None = None) -> str:
    validated_packages = validate_optional_packages(selected_packages or [])
    return render(
        "fix_errors.jinja2",
        errors=errors,
        files=files,
        allowed_imports=allowed_import_names(validated_packages),
        package_fix_rules=_render_optional_package_prompts(validated_packages, OptionalPackagePrompt.FIX_ERRORS_RULES),
        package_unselected_fix_rules=_render_unselected_optional_package_prompts(
            validated_packages, OptionalPackagePrompt.FIX_ERRORS_UNSELECTED_RULES
        ),
        file_safety=generated_app_path_safety_prompt_context(),
    )


def _render_optional_package_prompts(
    selected_packages: list[str] | None,
    prompt: OptionalPackagePrompt,
) -> list[str]:
    blocks: list[str] = []
    for package_name in validate_optional_packages(selected_packages or []):
        try:
            blocks.append(render(OPTIONAL_PACKAGES[package_name].prompt_template(prompt)).strip())
        except TemplateNotFound:
            continue
    return blocks


def _render_unselected_optional_package_prompts(
    selected_packages: list[str] | None,
    prompt: OptionalPackagePrompt,
) -> list[str]:
    selected = set(validate_optional_packages(selected_packages or []))
    blocks: list[str] = []
    for package_name, package in OPTIONAL_PACKAGES.items():
        if package_name in selected:
            continue
        try:
            blocks.append(render(package.prompt_template(prompt)).strip())
        except TemplateNotFound:
            continue
    return blocks


def _extract_exports(content: str) -> str:
    lines = content.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if re.match(r"^export\s", stripped):
            if re.match(r"^export\s+(interface|type)\s+\w+", stripped):
                block = [line]
                if "{" not in stripped or "}" in stripped:
                    result.append(line)
                    i += 1
                    continue
                i += 1
                brace_count = 1
                while i < len(lines) and brace_count > 0:
                    block.append(lines[i])
                    brace_count += lines[i].count("{") - lines[i].count("}")
                    i += 1
                result.extend(block)
            else:
                result.append(line)
                i += 1
        else:
            i += 1
    return "\n".join(result) if result else ""


# Constants
SUMMARY_PROMPT = render_summary()
