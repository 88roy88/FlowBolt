import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from langfuse.decorators import langfuse_context, observe
from pydantic import BaseModel

from flow44.ai.agents._base import BaseAgent
from flow44.ai.agents.followup.prompts import render_followup
from flow44.ai.core.messages import Message
from flow44.ai.core.react_flow import ReActFlow
from flow44.ai.core.tools import ToolExecutor, tool
from flow44.db.chat import get_messages
from flow44.db.project import get_project
from flow44.sandbox.main import PnpmSandbox

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 15


@dataclass
class FileDiff:
    path: str
    diff: str


class FollowUpAgent(BaseAgent):
    def __init__(
        self,
        project_id: str,
        sandbox: PnpmSandbox,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(project_id, sandbox, model=model, trace_id=trace_id)
        self._steps: list[dict[str, Any]] = []
        self._diffs: list[FileDiff] = []
        self._files_changed: list[str] = []
        self._iteration = 0
        self._executor = self._build_tool_executor()

    def _build_tool_executor(self) -> ToolExecutor:  # noqa: C901, PLR0915
        sandbox = self.sandbox

        # Inline tool implementations - thin wrappers around sandbox
        @tool
        async def grep(pattern: str, file_pattern: str | None = None) -> str:
            """Search the entire codebase for a text or regex pattern using grep.

            Use this to find all occurrences of functions, classes, variables, imports, or any text pattern.
            Much faster than reading files one by one — always prefer this over glob+read for searching code.

            Args:
                pattern: Text or regex pattern to search for (e.g., "useState", "import.*axios", "className=")
                file_pattern: Optional file glob to narrow search (e.g., "*.tsx", "*.css")

            Returns:
                Matching lines with file paths and line numbers
            """
            try:
                matches = await sandbox.grep(pattern, "/", file_pattern, max_results=50)
            except PermissionError as e:
                return f"Error: {e}"
            if not matches:
                return "No matches found."
            return "\n".join(f"{m.file}:{m.line}:{m.content}" for m in matches)

        @tool
        async def glob(pattern: str) -> str:
            """Find files matching a glob pattern. Returns file paths."""
            results = await sandbox.glob(pattern)
            if not results:
                return "No files found matching pattern."
            return "\n".join(results)

        @tool
        async def read_file(path: str) -> str:
            """Read the full content of a file with line numbers. Always read a file before editing it."""
            try:
                content = await sandbox.read_file(path)
            except (FileNotFoundError, PermissionError) as e:
                return f"Error: {e}"
            lines = content.splitlines()
            if len(lines) > 500:
                numbered = [f"{i + 1:4d} | {line}" for i, line in enumerate(lines[:500])]
                numbered.append(f"\n... (truncated at 500 lines, file has {len(lines)} total)")
                return "\n".join(numbered)
            return "\n".join(f"{i + 1:4d} | {line}" for i, line in enumerate(lines))

        @tool
        async def write_file(path: str, content: str) -> str:
            """Write the full content of a file, creating it if needed. For small changes, prefer edit_file."""
            import difflib  # noqa: PLC0415

            try:
                old_content = await sandbox.read_file(path)
            except FileNotFoundError:
                old_content = ""
            await sandbox.write_file(path, content)

            # Generate diff
            old_lines = old_content.splitlines(keepends=True)
            new_lines = content.splitlines(keepends=True)
            diff_str = "".join(
                difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="")
            )

            await self.emit({"type": "file", "path": path, "content": content})
            if diff_str:
                self._diffs.append(FileDiff(path=path, diff=diff_str))
            if path not in self._files_changed:
                self._files_changed.append(path)
            return f"OK — wrote {path} ({len(content.splitlines())} lines)"

        @tool
        async def edit_file(path: str, search: str, replace: str) -> str:
            """Apply a targeted search-and-replace edit. The search string must match exactly."""
            import difflib  # noqa: PLC0415

            try:
                current = await sandbox.read_file(path)
            except FileNotFoundError:
                return f"Error: File not found: {path}"

            try:
                await sandbox.edit_file(path, search, replace)
            except ValueError:
                lines = current.splitlines()
                snippet = "\n".join(lines[:40])
                if len(lines) > 40:
                    snippet += f"\n... ({len(lines)} lines total)"
                return (
                    f"Error: search string not found in {path}. "
                    f"The search must match exactly (including whitespace).\n\n"
                    f"Current file content:\n```\n{snippet}\n```"
                )

            new_content = await sandbox.read_file(path)

            # Generate diff
            old_lines = current.splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)
            diff_str = "".join(
                difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="")
            )

            await self.emit({"type": "file", "path": path, "content": new_content})
            if diff_str:
                self._diffs.append(FileDiff(path=path, diff=diff_str))
            if path not in self._files_changed:
                self._files_changed.append(path)
            return f"OK — edited {path}"

        return ToolExecutor([grep, glob, read_file, write_file, edit_file])

    @observe(name="followup-agent-run")  # type: ignore[untyped-decorator]
    async def run(self, content: str) -> None:
        langfuse_context.update_current_observation(tags=["follow-up-agent"])
        # TODO: add metadata. like SID  # noqa: E501
        # (also, we need to standardize session id and project id usage across the codebase).

        await self.emit({"type": "phase", "phase": "exploring"})
        context = await self._build_context()

        # TODO: fix, after change to messages in db, we dont get internal chat history anymore.
        history = await get_messages(self.project_id)
        messages = [
            Message(role=m.role, content=m.content)  # type: ignore[arg-type]
            for m in history
            if m.role == "user" or (m.role == "assistant" and m.content.strip())
        ]

        system_prompt = render_followup(
            project_summary=context["summary"],
            file_tree=context["file_tree"],
        )

        react_flow: ReActFlow[BaseModel] = ReActFlow(name="followup", max_iterations=MAX_ITERATIONS)
        answer = await react_flow.react_loop(
            messages=messages,
            system_prompt=system_prompt,
            tools=self._executor,
            model=self.model,
            metadata_fn=lambda step: self._llm_metadata(f"followup-{step}"),
            emit_fn=self._emit_react_step,
        )

        if answer:
            await self.emit({"type": "text", "content": answer})

        if self._diffs:
            await self.emit(
                {
                    "type": "followup_diffs",
                    "diffs": [{"path": d.path, "diff": d.diff} for d in self._diffs],
                }
            )

        # TODO: do we need both events?
        await self.emit({"type": "phase", "phase": "complete"})
        await self.emit({"type": "action_complete"})

    # TODO: We will want to have a smarted memory system in the future
    async def _build_context(self) -> dict[str, str]:
        project = await get_project(self.project_id)
        summary = ""
        if project and project.summary:
            try:
                data = json.loads(project.summary)
                summary = (
                    f"{data.get('summary', '')}\n"
                    f"Tech stack: {', '.join(data.get('tech_stack', []))}\n"
                    f"Features: {', '.join(data.get('features', []))}\n"
                )
            except (json.JSONDecodeError, AttributeError):
                summary = "(no project summary available)"

        try:
            file_entries = await self.sandbox.list_files()
            file_tree = self._format_file_tree(file_entries)
        except Exception:
            file_tree = "(unable to list files)"

        return {"summary": summary, "file_tree": file_tree}

    async def _emit_react_step(self, event: dict[str, Any]) -> None:
        """Emit ReAct step events and track state for followup agent."""
        if event["type"] == "react_step":
            self._iteration = event["iteration"]
            step_data = {
                "tool": event["tool"],
                "args": event.get("args", {}),
                "status": event["status"],
                "iteration": self._iteration,
            }
            if event["status"] == "completed":
                step_data["result_preview"] = event.get("result_preview", "")
                self._steps.append(
                    {
                        "id": str(uuid.uuid4()),
                        "tool": event["tool"],
                        "args": event.get("args", {}),
                        "status": "completed",
                        "resultPreview": event.get("result_preview", ""),
                        "iteration": self._iteration,
                    }
                )
            await self.emit({"type": "followup_step", **step_data})

    # TODO: feels like a general utils that should go out.
    def _format_file_tree(self, entries: list[Any], indent: int = 0) -> str:
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

    # TODO: should we add a step to update the summary?
    # TODO: think about cases where the follow up is a big request that requires maybe recall the build agent.
