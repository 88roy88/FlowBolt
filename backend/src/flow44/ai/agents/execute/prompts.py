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


def render_merge(*, has_data_sources: bool = False) -> str:
    return render("merge.jinja2", has_data_sources=has_data_sources)


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
) -> str:
    prepared_sources = None
    if data_source_contexts:
        prepared_sources = []
        for ctx in data_source_contexts:
            prepared_sources.append(
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
        data_source_contexts=prepared_sources,
    )


def render_fix_errors(*, errors: str, files: dict[str, str]) -> str:
    return render("fix_errors.jinja2", errors=errors, files=files)


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
