from __future__ import annotations

from pathlib import Path
from typing import Literal, overload

from jinja2 import ChoiceLoader, Environment, FileSystemLoader

from flow44.ai.agents.optional_packages import (
    OptionalPackagePrompt,
    allowed_import_names,
    render_optional_package_prompts,
    render_unselected_optional_package_prompts,
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
    template_name: Literal["followup.jinja2"],
    *,
    project_summary: str,
    file_tree: str,
    allowed_imports: list[str],
    package_contexts: list[str],
    package_rules: list[str],
    package_unselected_rules: list[str],
    file_safety: GeneratedAppPathSafetyPromptContext,
) -> str: ...


@overload
def render(template_name: str) -> str: ...


def render(template_name: str, **kwargs: object) -> str:
    return _env.get_template(template_name).render(**kwargs)


def render_followup(
    *,
    project_summary: str,
    file_tree: str,
    selected_packages: list[str] | None = None,
    include_optional_package_prompts: bool = True,
) -> str:
    validated_packages = validate_optional_packages(selected_packages or [])
    return render(
        "followup.jinja2",
        project_summary=project_summary,
        file_tree=file_tree,
        allowed_imports=allowed_import_names(validated_packages),
        package_contexts=render_optional_package_prompts(
            validated_packages,
            OptionalPackagePrompt.CODEGEN_CONTEXT,
            render,
            enabled=include_optional_package_prompts,
        ),
        package_rules=render_optional_package_prompts(
            validated_packages,
            OptionalPackagePrompt.CODEGEN_RULES,
            render,
            enabled=include_optional_package_prompts,
        ),
        package_unselected_rules=render_unselected_optional_package_prompts(
            validated_packages,
            OptionalPackagePrompt.CODEGEN_UNSELECTED_RULES,
            render,
            enabled=include_optional_package_prompts,
        ),
        file_safety=generated_app_path_safety_prompt_context(),
    )
