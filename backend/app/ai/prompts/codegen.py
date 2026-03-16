"""Prompt for generating code for a specific task."""


def get_codegen_prompt(
    task_title: str,
    task_description: str,
    task_files: list[str],
    architecture: dict,
    ux_design: dict,
    completed_files: dict[str, str] | None = None,
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
    completed_files:
        Dict of {path: content} for files already written by prior tasks,
        so the model can import from them correctly.
    """
    completed_section = ""
    if completed_files:
        file_summaries = []
        for path, content in completed_files.items():
            # Include a truncated view so the model knows what's available
            lines = content.split("\n")
            preview = "\n".join(lines[:50])
            if len(lines) > 50:
                preview += f"\n... ({len(lines) - 50} more lines)"
            file_summaries.append(f"### {path}\n```\n{preview}\n```")
        completed_section = (
            "\n\n## Already-completed files (for reference — do NOT rewrite these)\n\n"
            + "\n\n".join(file_summaries)
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
2. Use TypeScript, React 18+, and Tailwind CSS.
3. Write clean, production-quality code.
4. Only output the files listed above — do not create extra files.
5. Import from already-completed files using their exact export names.
6. Do NOT include shell actions — only file actions.
"""


def _compact_json(data: dict) -> str:
    import json
    return json.dumps(data, indent=2, ensure_ascii=False)
