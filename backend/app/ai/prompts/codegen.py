"""Prompt for generating code for a specific task."""

import re


def get_codegen_prompt(
    task_title: str,
    task_description: str,
    task_files: list[str],
    architecture: dict,
    ux_design: dict,
    package_data: dict | None = None,
    dependency_files: dict[str, str] | None = None,
    other_completed_files: dict[str, str] | None = None,
) -> str:
    """Build a focused code-generation prompt for a single task.

    Parameters
    ----------
    task_title:
        Human-readable task name.
    task_description:
        What this task should produce.
    task_files:
        File paths this task must generate.
    architecture:
        The full architecture design dict (for context).
    ux_design:
        The full UX design dict (for context).
    package_data:
        Dict returned from running the selected package (if any).
    dependency_files:
        Dict of {path: content} for files produced by direct dependency tasks.
        These are included in full so the model can import from them correctly.
    other_completed_files:
        Dict of {path: content} for files from non-dependency tasks.
        Only export summaries are shown to save tokens.
    """
    completed_section = ""
    parts: list[str] = []

    # Full content for direct dependency files
    if dependency_files:
        dep_parts = []
        for path, content in dependency_files.items():
            dep_parts.append(f"### {path} (full — direct dependency)\n```\n{content}\n```")
        if dep_parts:
            parts.append(
                "## Direct dependency files (full content — import from these)\n\n"
                + "\n\n".join(dep_parts)
            )

    # Export summaries for other completed files
    if other_completed_files:
        other_parts = []
        for path, content in other_completed_files.items():
            exports = _extract_exports(content)
            if exports:
                other_parts.append(f"### {path} (exports)\n```\n{exports}\n```")
            else:
                # Fallback: truncated preview for non-parseable files (CSS, JSON, etc.)
                lines = content.split("\n")
                preview = "\n".join(lines[:50])
                if len(lines) > 50:
                    preview += f"\n... ({len(lines) - 50} more lines)"
                other_parts.append(f"### {path}\n```\n{preview}\n```")
        if other_parts:
            parts.append(
                "## Other completed files (exports only — do NOT rewrite these)\n\n"
                + "\n\n".join(other_parts)
            )

    if parts:
        completed_section = "\n\n" + "\n\n".join(parts)

    package_section = ""
    if package_data is not None:
        package_section = (
            "\n\n## Package data (from running the selected package)\n"
            "Use this as the primary dataset to display in the generated UI.\n\n"
            "```json\n"
            f"{_compact_json(package_data)}\n"
            "```"
        )

    return f"""\
You are an expert React/TypeScript developer. You are implementing a specific task
as part of a larger project.

## Your Task
**{task_title}**
{task_description}

## Files to generate
{chr(10).join(f"- {f}" for f in task_files)}

## Architecture Context
```json
{_compact_json(architecture)}
```

## UI/UX Context
```json
{_compact_json(ux_design)}
```
{package_section}
{completed_section}

## Output Format

Respond using the boltArtifact XML format. Write COMPLETE file contents — no
placeholders or ellipses.

```xml
<boltArtifact id="task-output" title="{task_title}">
  <boltAction type="file" filePath="path/relative/to/project/root">
    Full file content here
  </boltAction>
</boltArtifact>
```

Rules:
1. All file paths are relative to the project root (e.g. src/App.tsx).
2. Use TypeScript, React 18+, and Tailwind CSS v3.
3. Tailwind CSS is pre-configured - use utility classes extensively for styling.
4. Write clean, production-quality code with modern, polished UI/UX.
5. Only output the files listed above — do not create extra files.
6. **CRITICAL**: Only React, TypeScript, and Tailwind CSS are available. Do NOT use or import other npm packages (no axios, lodash, zustand, date-fns, clsx, etc.). All functionality must be implemented using built-in browser APIs and the pre-installed packages only.
7. Import from already-completed files using their exact export names.
8. Do NOT include shell actions — only file actions.
"""


def _extract_exports(content: str) -> str:
    """Extract export statements from TypeScript/TSX content.

    Returns a compact string of all exports: function signatures, type/interface
    definitions, and const declarations.  For function/component exports only
    the signature line is kept (not the body).  For interface/type exports the
    full block is included (they're usually short).
    """
    lines = content.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Match lines starting with 'export'
        if re.match(r"^export\s", stripped):
            # Interface or type block — capture until closing brace
            if re.match(r"^export\s+(interface|type)\s+\w+", stripped):
                block = [line]
                # If it's a single-line type alias (no opening brace or has closing on same line)
                if "{" not in stripped or ("}" in stripped):
                    result.append(line)
                    i += 1
                    continue
                # Multi-line: capture until balanced braces
                depth = stripped.count("{") - stripped.count("}")
                i += 1
                while i < len(lines) and depth > 0:
                    block.append(lines[i])
                    depth += lines[i].count("{") - lines[i].count("}")
                    i += 1
                result.extend(block)
                continue

            # Function or const — just the signature line
            result.append(line)
            i += 1
            continue

        i += 1

    return "\n".join(result)


def _compact_json(data: dict) -> str:
    import json
    return json.dumps(data, indent=2, ensure_ascii=False)
