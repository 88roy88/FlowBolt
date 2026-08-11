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
from flow44.db.project_data_source import DataSourceContext

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
    file_safety: ProtectedFileRules,
    new_data_source_contexts: list[DataSourceContext] | None,
    existing_data_source_contexts: list[DataSourceContext] | None,
    installed_packages: list[str] | None,
    package_rules: list[str] | None,
) -> str: ...


@overload
def render(template_name: str) -> str: ...


def render(template_name: str, **kwargs: object) -> str:
    return _env.get_template(template_name).render(**kwargs)


def render_followup(
    *,
    project_summary: str,
    file_tree: str,
    new_data_source_contexts: list[DataSourceContext] | None = None,
    existing_data_source_contexts: list[DataSourceContext] | None = None,
    installed_packages: list[str] | None = None,
) -> str:
    return render(
        "followup.jinja2",
        project_summary=project_summary,
        file_tree=file_tree,
        file_safety=protected_file_rules(),
        new_data_source_contexts=new_data_source_contexts,
        existing_data_source_contexts=existing_data_source_contexts,
        installed_packages=installed_packages or None,
        package_rules=render_package_rules(installed_packages or [], PackageRuleset.FOLLOWUP) or None,
    )
