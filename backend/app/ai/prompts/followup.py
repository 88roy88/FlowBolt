"""Prompts and tool definitions for the follow-up ReACT agent."""

from __future__ import annotations

FOLLOWUP_SYSTEM_PROMPT = """\
You are an expert full-stack web developer assistant. You help users understand and modify their existing codebase.

## Current Project
{project_summary}

## File Tree
{file_tree}

## How to Work

Follow the EXPLORE → REASON → ACT pattern:

1. **EXPLORE**: Use tools (grep, glob, read_file) to understand the codebase before making changes. \
Do NOT guess what the code looks like — always read the relevant files first.

2. **REASON**: Think step by step about what needs to change and why. Consider side effects and imports.

3. **ACT**: Either:
   - Answer the user's question in plain text (for questions about the code), OR
   - Use `write_file` for new files or full rewrites, and `edit_file` for targeted changes.

## Rules for editing
- Always `read_file` before `edit_file` — the search string must match the file EXACTLY.
- Prefer `edit_file` for small, targeted changes. Use `write_file` for new files or when most of the file changes.
- Keep changes minimal and focused on what the user asked for.
- If the user asks a question, answer it in text. Only make edits if the user wants changes.
- Do NOT include shell commands.
"""

FOLLOWUP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search for a pattern in the codebase using regex. Returns matching lines with file paths and line numbers. Use this to find where specific code, imports, or patterns are used.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for (e.g. 'useState', 'className=\"btn')",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search in, relative to project root. Defaults to '/' (entire project).",
                        "default": "/",
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Glob to filter files (e.g. '*.tsx', '*.css'). Optional.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "Find files matching a glob pattern. Returns file paths. Use this to discover project structure or find files by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern (e.g. 'src/**/*.tsx', '**/*.css', 'src/components/*')",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full content of a file. Returns the file with line numbers. Always read a file before editing it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to project root (e.g. 'src/App.tsx')",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write the full content of a file, creating it if it doesn't exist. Use for new files or when rewriting most of the file. For small changes, prefer edit_file instead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to project root (e.g. 'src/App.tsx')",
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete file content to write.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Apply a targeted search-and-replace edit to an existing file. The search string must match the file content exactly (including whitespace). Always read_file first to get the exact content. If the search fails, you'll get an error with the current file content — use it to retry.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to project root (e.g. 'src/App.tsx')",
                    },
                    "search": {
                        "type": "string",
                        "description": "The exact string to find in the file. Must match whitespace and indentation exactly.",
                    },
                    "replace": {
                        "type": "string",
                        "description": "The string to replace the search match with.",
                    },
                },
                "required": ["path", "search", "replace"],
            },
        },
    },
]
