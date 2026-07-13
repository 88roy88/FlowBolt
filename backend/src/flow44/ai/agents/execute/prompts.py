from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal, overload

from jinja2 import ChoiceLoader, Environment, FileSystemLoader

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
    template_name: Literal["merge.jinja2"],
    *,
    has_data_sources: bool,
    allowed_packages: list[str] | None,
    package_rules: list[str] | None,
    file_safety: ProtectedFileRules,
) -> str: ...


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
    allowed_packages: list[str] | None,
    package_rules: list[str] | None,
    file_safety: ProtectedFileRules,
) -> str: ...


@overload
def render(
    template_name: Literal["feedback.jinja2"],
    *,
    files: dict[str, str],
    package_rules: list[str] | None,
    file_safety: ProtectedFileRules,
) -> str: ...


@overload
def render(template_name: str) -> str: ...


def render(template_name: str, **kwargs: object) -> str:
    return _env.get_template(template_name).render(**kwargs)


def render_merge(
    *,
    has_data_sources: bool = False,
    allowed_packages: list[str] | None = None,
    package_rules: list[str] | None = None,
) -> str:
    return render(
        "merge.jinja2",
        has_data_sources=has_data_sources,
        allowed_packages=allowed_packages or None,
        package_rules=package_rules or None,
        file_safety=protected_file_rules(),
    )


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
    data_source_contexts: list[DataSourceContext] | None = None,
    allowed_packages: list[str] | None = None,
    package_rules: list[str] | None = None,
) -> str:
    prepared_sources = [ctx.to_prompt_context() for ctx in data_source_contexts] if data_source_contexts else None

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
        allowed_packages=allowed_packages or None,
        package_rules=package_rules or None,
        file_safety=protected_file_rules(),
    )


def render_feedback(*, files: dict[str, str], package_rules: list[str] | None = None) -> str:
    return render(
        "feedback.jinja2",
        files=files,
        package_rules=package_rules or None,
        file_safety=protected_file_rules(),
    )


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
