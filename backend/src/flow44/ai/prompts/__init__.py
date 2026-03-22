from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

_templates_dir = Path(__file__).parent / "templates"
_env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML; autoescape would break them
    loader=FileSystemLoader(str(_templates_dir)), trim_blocks=True, lstrip_blocks=True
)


def render(template_name: str, **kwargs: Any) -> str:
    return _env.get_template(template_name).render(**kwargs)


def render_classify() -> str:
    return render("classify.jinja2")


def render_architecture(*, case_contexts: list[dict] | None = None) -> str:
    prepared = None
    if case_contexts:
        prepared = [
            {**ctx, "sample_data_json": json.dumps(ctx.get("sample_data", {}), indent=2)[:1000]}
            for ctx in case_contexts
        ]
    return render("architecture.jinja2", case_contexts=prepared)


def render_ux_design() -> str:
    return render("ux_design.jinja2")


def render_merge(*, has_cases: bool = False) -> str:
    return render("merge.jinja2", has_cases=has_cases)


def render_user_plan(*, has_feedback: bool = False) -> str:
    return render("user_plan.jinja2", has_feedback=has_feedback)


def render_summary() -> str:
    return render("summary.jinja2")


def render_followup(*, project_summary: str, file_tree: str) -> str:
    return render("followup.jinja2", project_summary=project_summary, file_tree=file_tree)


def render_codegen(
    *,
    task_title: str,
    task_description: str,
    task_files: list[str],
    architecture: dict,
    ux_design: dict,
    dependency_files: dict[str, str] | None = None,
    other_completed_files: dict[str, str] | None = None,
    case_contexts: list[dict] | None = None,
) -> str:
    prepared_cases = None
    if case_contexts:
        prepared_cases = []
        for ctx in case_contexts:
            prepared_cases.append(
                {
                    **ctx,
                    "sample_data_json": json.dumps(ctx.get("sample_data", {}), indent=2)[:1000],
                }
            )

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
        case_contexts=prepared_cases,
    )


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


# Backward-compatible exports used by agent.py until fully migrated
CLASSIFY_PROMPT = render_classify()
ARCHITECTURE_PROMPT = render_architecture()
UX_DESIGN_PROMPT = render_ux_design()
MERGE_PROMPT = render_merge()
USER_PLAN_PROMPT = render_user_plan()
SUMMARY_PROMPT = render_summary()
get_codegen_prompt = render_codegen


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
                depth = stripped.count("{") - stripped.count("}")
                i += 1
                while i < len(lines) and depth > 0:
                    block.append(lines[i])
                    depth += lines[i].count("{") - lines[i].count("}")
                    i += 1
                result.extend(block)
                continue
            result.append(line)
            i += 1
            continue
        i += 1
    return "\n".join(result)
