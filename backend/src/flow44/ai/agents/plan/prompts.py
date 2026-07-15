from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, overload

from jinja2 import ChoiceLoader, Environment, FileSystemLoader

from flow44.ai.agents.optional_packages import OPTIONAL_PACKAGES, OptionalPackage, resolve_packages
from flow44.ai.agents.template_paths import TEMPLATE_PROMPTS_PATH
from flow44.ai.file_safety import (
    ProtectedFileRules,
    protected_file_rules,
)
from flow44.db.project_data_source import DataSourceContext

_templates_dir = Path(__file__).parent / "templates"
_env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML; autoescape would break them
    loader=ChoiceLoader([FileSystemLoader(str(_templates_dir)), FileSystemLoader(str(TEMPLATE_PROMPTS_PATH))]),
    trim_blocks=True,
    lstrip_blocks=True,
)


@overload
def render(
    template_name: Literal["architecture.jinja2"],
    *,
    data_source_contexts: list[dict[str, Any]] | None,
    selected_packages: list[OptionalPackage] | None,
    file_safety: ProtectedFileRules,
) -> str: ...


@overload
def render(template_name: Literal["package_decision.jinja2"], *, packages: list[OptionalPackage]) -> str: ...


@overload
def render(template_name: Literal["ux_design.jinja2"]) -> str: ...


@overload
def render(template_name: Literal["user_plan.jinja2"], *, has_feedback: bool) -> str: ...


@overload
def render(
    template_name: Literal["data_source_analysis.jinja2"],
    *,
    user_content: str,
    data_source_name: str,
    sample_data_json: str | None,
    queries: list[dict[str, Any]],
    params: list[dict[str, Any]],
    require_any: bool,
) -> str: ...


def render(template_name: str, **kwargs: object) -> str:
    return _env.get_template(template_name).render(**kwargs)


def render_package_decision() -> str:
    return render("package_decision.jinja2", packages=list(OPTIONAL_PACKAGES.values()))


def render_architecture(
    *,
    data_source_contexts: list[DataSourceContext] | None = None,
    selected_package_names: list[str] | None = None,
) -> str:
    prepared = [ctx.to_prompt_context() for ctx in data_source_contexts] if data_source_contexts else None
    return render(
        "architecture.jinja2",
        data_source_contexts=prepared,
        selected_packages=resolve_packages(selected_package_names or []),
        file_safety=protected_file_rules(),
    )


def render_ux_design() -> str:
    return render("ux_design.jinja2")


def render_user_plan(*, has_feedback: bool = False) -> str:
    return render("user_plan.jinja2", has_feedback=has_feedback)


def render_data_source_analysis(
    *,
    user_content: str,
    data_source_name: str,
    sample_data: Any,
    queries: list[dict[str, Any]] | None = None,
    params_info: dict[str, Any] | None = None,
) -> str:
    sample_json = json.dumps(sample_data, indent=2)[:2000] if sample_data else None
    return render(
        "data_source_analysis.jinja2",
        user_content=user_content,
        data_source_name=data_source_name,
        sample_data_json=sample_json,
        queries=queries or [],
        params=(params_info or {}).get("parameters", []),
        require_any=(params_info or {}).get("require_any", False),
    )


# Constants
UX_DESIGN_PROMPT = render_ux_design()
