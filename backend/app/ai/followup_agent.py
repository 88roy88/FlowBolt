"""ReACT-loop follow-up agent for codebase exploration and targeted edits."""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
import uuid
from collections.abc import Callable, Awaitable
from dataclasses import dataclass
from pathlib import Path

from langfuse.decorators import observe, langfuse_context

from app.ai.provider import complete_chat_with_tools
from app.ai.prompts.followup import FOLLOWUP_SYSTEM_PROMPT, FOLLOWUP_TOOLS
from app.models.chat import get_messages, save_message
from app.models.project import get_project_by_session
from app.sandbox.filesystem import read_file, write_file, edit_file, list_files
from app.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

CARD_PREFIX = "<!--agent-card:"
CARD_SUFFIX = "-->"

MAX_ITERATIONS = 15


@dataclass
class FileDiff:
    path: str
    diff: str  # unified diff string


def _encode_card(card_data: dict) -> str:
    return f"{CARD_PREFIX}{json.dumps(card_data, separators=(',', ':'))}{CARD_SUFFIX}"


def _make_diff(path: str, old: str, new: str) -> str:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    return "".join(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{path}", tofile=f"b/{path}",
        lineterm="",
    ))


class FollowUpAgent:
    """ReACT agent that explores the codebase before making targeted edits."""

    def __init__(
        self,
        session_id: str,
        project_id: str,
        ws_send: Callable[[dict], Awaitable[None]],
        model: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.session_id = session_id
        self.project_id = project_id
        self.ws_send = ws_send
        self.model = model
        self.trace_id = trace_id
        self._steps: list[dict] = []
        self._diffs: list[FileDiff] = []
        self._files_changed: list[str] = []
        self._iteration = 0

    def _llm_metadata(self, generation_name: str) -> dict:
        trace_id = self.trace_id or langfuse_context.get_current_trace_id()
        observation_id = langfuse_context.get_current_observation_id()
        return {
            "existing_trace_id": trace_id,
            "parent_observation_id": observation_id,
            "generation_name": generation_name,
        }

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    @observe(name="followup-run")
    async def run(self, content: str) -> None:
        """Process a follow-up message using the ReACT loop."""
        langfuse_context.update_current_observation(
            tags=["follow-up-agent"],
        )

        # 1. Build context
        await self.ws_send({"type": "phase", "phase": "exploring"})
        context = await self._build_context()

        # 2. Load chat history
        history = await get_messages(self.project_id)
        messages = [
            {"role": m.role, "content": m.content}
            for m in history
            if not m.content.startswith(CARD_PREFIX)
        ]

        # 3. ReACT loop (tools handle both reads AND writes)
        system_prompt = FOLLOWUP_SYSTEM_PROMPT.format(
            project_summary=context["summary"],
            file_tree=context["file_tree"],
        )
        answer = await self._react_loop(messages, system_prompt)

        # 4. Stream the final text answer to the client
        if answer:
            await self.ws_send({"type": "text", "content": answer})

        # 5. Save message and send completion
        card = _encode_card({
            "type": "followup_progress",
            "steps": self._steps,
            "answer": answer or None,
            "filesChanged": self._files_changed,
            "diffs": [{"path": d.path, "diff": d.diff} for d in self._diffs],
        })
        assistant_content = (answer + "\n" + card) if answer else card
        await save_message(self.project_id, "assistant", assistant_content)

        # Send diffs to frontend for live card rendering
        if self._diffs:
            await self.ws_send({
                "type": "followup_diffs",
                "diffs": [{"path": d.path, "diff": d.diff} for d in self._diffs],
            })

        await self.ws_send({"type": "phase", "phase": "complete"})
        await self.ws_send({"type": "action_complete"})

    # ------------------------------------------------------------------
    # Context building
    # ------------------------------------------------------------------

    @observe(name="followup-build-context")
    async def _build_context(self) -> dict:
        project = await get_project_by_session(self.session_id)
        summary = ""
        if project and project.summary:
            try:
                summary_data = json.loads(project.summary)
                summary = (
                    f"{summary_data.get('summary', '')}\n"
                    f"Tech stack: {', '.join(summary_data.get('tech_stack', []))}\n"
                    f"Features: {', '.join(summary_data.get('features', []))}\n"
                )
            except (json.JSONDecodeError, AttributeError):
                summary = "(no project summary available)"

        try:
            file_entries = await list_files(self.session_id)
            file_tree = self._format_file_tree(file_entries)
        except Exception:
            file_tree = "(unable to list files)"

        return {"summary": summary, "file_tree": file_tree}

    def _format_file_tree(self, entries, indent: int = 0) -> str:
        lines = []
        for entry in entries:
            prefix = "  " * indent
            if entry.is_directory:
                lines.append(f"{prefix}{entry.name}/")
                if entry.children:
                    lines.append(self._format_file_tree(entry.children, indent + 1))
            else:
                lines.append(f"{prefix}{entry.name}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # ReACT loop
    # ------------------------------------------------------------------

    @observe(name="followup-react-loop")
    async def _react_loop(self, messages: list[dict], system_prompt: str) -> str:
        """Core ReACT loop: call LLM, execute tools, repeat until done."""
        working_messages = list(messages)
        last_content = ""

        for self._iteration in range(MAX_ITERATIONS):
            response = await complete_chat_with_tools(
                messages=working_messages,
                system_prompt=system_prompt,
                tools=FOLLOWUP_TOOLS,
                model=self.model,
                metadata=self._llm_metadata(f"followup-react-{self._iteration}"),
            )

            choice = response.choices[0]
            message = choice.message
            last_content = message.content or ""

            if not message.tool_calls:
                return last_content

            working_messages.append(message.model_dump())

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                # Send running step
                step_data = {
                    "tool": tool_name,
                    "args": {k: v for k, v in args.items() if k != "content"},
                    "status": "running",
                    "iteration": self._iteration,
                }
                await self.ws_send({"type": "followup_step", **step_data})

                # Execute tool
                result = await self._execute_tool(tool_name, args)

                # Send completed step
                preview = result[:200] + "..." if len(result) > 200 else result
                step_data["status"] = "completed"
                step_data["result_preview"] = preview
                await self.ws_send({"type": "followup_step", **step_data})

                # Track step for card persistence
                self._steps.append({
                    "id": str(uuid.uuid4()),
                    "tool": tool_name,
                    "args": {k: v for k, v in args.items() if k != "content"},
                    "status": "completed",
                    "resultPreview": preview,
                    "iteration": self._iteration,
                })

                working_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

        logger.warning("[followup-agent] Hit max iterations (%d)", MAX_ITERATIONS)
        return last_content

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    @observe(name="followup-execute-tool")
    async def _execute_tool(self, tool_name: str, args: dict) -> str:
        try:
            if tool_name == "grep":
                return await self._tool_grep(
                    args["pattern"],
                    args.get("path", "/"),
                    args.get("file_pattern"),
                )
            elif tool_name == "glob":
                return await self._tool_glob(args["pattern"])
            elif tool_name == "read_file":
                return await self._tool_read_file(args["path"])
            elif tool_name == "write_file":
                return await self._tool_write_file(args["path"], args["content"])
            elif tool_name == "edit_file":
                return await self._tool_edit_file(
                    args["path"], args["search"], args["replace"],
                )
            else:
                return f"Unknown tool: {tool_name}"
        except Exception as e:
            return f"Error: {e}"

    async def _tool_grep(self, pattern: str, path: str = "/", file_pattern: str | None = None) -> str:
        """Run ripgrep in the sandbox workspace."""
        sandbox = sandbox_manager.get_sandbox(self.session_id)
        if sandbox is None:
            return "Error: No sandbox found"

        workspace = os.path.realpath(sandbox.workspace_dir)
        search_path = os.path.realpath(os.path.join(workspace, path.lstrip("/")))

        if not search_path.startswith(workspace):
            return "Error: Path traversal detected"

        cmd = [
            "rg", "--no-heading", "--line-number", "--max-count", "50",
            "--glob", "!node_modules",
            "--glob", "!.git",
            "--glob", "!dist",
            "--glob", "!.next",
        ]
        if file_pattern:
            cmd.extend(["--glob", file_pattern])
        cmd.extend([pattern, search_path])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            output = stdout.decode("utf-8", errors="replace")

            lines = []
            for line in output.splitlines()[:50]:
                if line.startswith(workspace):
                    line = line[len(workspace):]
                lines.append(line)

            if not lines:
                return "No matches found."
            return "\n".join(lines)
        except asyncio.TimeoutError:
            return "Error: grep timed out"
        except FileNotFoundError:
            return "Error: ripgrep (rg) not available"

    async def _tool_glob(self, pattern: str) -> str:
        """Find files matching a glob pattern in the sandbox."""
        sandbox = sandbox_manager.get_sandbox(self.session_id)
        if sandbox is None:
            return "Error: No sandbox found"

        workspace = Path(os.path.realpath(sandbox.workspace_dir))
        SKIP = {"node_modules", ".git", "dist", ".next", ".cache", "__pycache__"}

        results = []
        for p in workspace.glob(pattern):
            if any(part in SKIP for part in p.parts):
                continue
            rel = "/" + str(p.relative_to(workspace))
            results.append(rel)
            if len(results) >= 100:
                break

        if not results:
            return "No files found matching pattern."
        return "\n".join(sorted(results))

    async def _tool_read_file(self, path: str) -> str:
        """Read a file from the sandbox with line numbers."""
        try:
            content = await read_file(self.session_id, path)
        except (FileNotFoundError, PermissionError) as e:
            return f"Error: {e}"

        lines = content.splitlines()
        if len(lines) > 500:
            lines = lines[:500]
            numbered = [f"{i + 1:4d} | {line}" for i, line in enumerate(lines)]
            numbered.append(f"\n... (truncated at 500 lines, file has {len(content.splitlines())} total)")
            return "\n".join(numbered)

        return "\n".join(f"{i + 1:4d} | {line}" for i, line in enumerate(lines))

    async def _tool_write_file(self, path: str, content: str) -> str:
        """Write full file content, creating it if needed. Returns diff."""
        try:
            old_content = await read_file(self.session_id, path)
        except FileNotFoundError:
            old_content = ""

        await write_file(self.session_id, path, content)
        await self.ws_send({"type": "file", "path": path, "content": content})

        diff_str = _make_diff(path, old_content, content)
        if diff_str:
            self._diffs.append(FileDiff(path=path, diff=diff_str))
        if path not in self._files_changed:
            self._files_changed.append(path)

        return f"OK — wrote {path} ({len(content.splitlines())} lines)"

    async def _tool_edit_file(self, path: str, search: str, replace: str) -> str:
        """Search-and-replace edit. Returns diff on success, error with file content on failure."""
        try:
            current = await read_file(self.session_id, path)
        except FileNotFoundError:
            return f"Error: File not found: {path}"

        try:
            await edit_file(self.session_id, path, search, replace)
        except ValueError:
            lines = current.splitlines()
            snippet = "\n".join(lines[:40])
            if len(lines) > 40:
                snippet += f"\n... ({len(lines)} lines total)"
            return (
                f"Error: search string not found in {path}. "
                f"The search must match the file exactly (including whitespace).\n\n"
                f"Current file content:\n```\n{snippet}\n```"
            )

        new_content = await read_file(self.session_id, path)
        await self.ws_send({"type": "file", "path": path, "content": new_content})

        diff_str = _make_diff(path, current, new_content)
        if diff_str:
            self._diffs.append(FileDiff(path=path, diff=diff_str))
        if path not in self._files_changed:
            self._files_changed.append(path)

        return f"OK — edited {path}"
