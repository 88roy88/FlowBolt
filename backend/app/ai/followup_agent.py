from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable, Awaitable
from dataclasses import dataclass

from langfuse.decorators import observe, langfuse_context

from app.ai.core.tools import FunctionTool, ToolExecutor
from app.ai.core.messages import Message
from app.ai.provider import complete_chat_with_tools
from app.ai.prompts import render_followup
from app.ai.helpers import CARD_PREFIX, encode_card
from app.ai.tools.grep import grep
from app.ai.tools.glob import glob
from app.ai.tools.read_file import read_file_with_lines
from app.ai.tools.write_file import write_file_with_diff
from app.ai.tools.edit_file import edit_file_with_context
from app.models.chat import get_messages, save_message
from app.models.project import get_project_by_session
from app.sandbox.filesystem import list_files, read_file

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 15


@dataclass
class FileDiff:
    path: str
    diff: str


class FollowUpAgent:

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

        self._executor = self._build_tool_executor()

    def _build_tool_executor(self) -> ToolExecutor:
        sid = self.session_id

        async def _grep(pattern: str, path: str = "/", file_pattern: str | None = None) -> str:
            """Search for a pattern in the codebase using regex. Returns matching lines with file paths and line numbers."""
            return await grep(sid, pattern, path, file_pattern)

        async def _glob(pattern: str) -> str:
            """Find files matching a glob pattern. Returns file paths."""
            return await glob(sid, pattern)

        async def _read_file(path: str) -> str:
            """Read the full content of a file with line numbers. Always read a file before editing it."""
            return await read_file_with_lines(sid, path)

        async def _write_file(path: str, content: str) -> str:
            """Write the full content of a file, creating it if needed. For small changes, prefer edit_file."""
            status, diff_str = await write_file_with_diff(sid, path, content)
            await self.ws_send({"type": "file", "path": path, "content": content})
            if diff_str:
                self._diffs.append(FileDiff(path=path, diff=diff_str))
            if path not in self._files_changed:
                self._files_changed.append(path)
            return status

        async def _edit_file(path: str, search: str, replace: str) -> str:
            """Apply a targeted search-and-replace edit. The search string must match exactly."""
            status, diff_str = await edit_file_with_context(sid, path, search, replace)
            if diff_str:
                new_content = await read_file(sid, path)
                await self.ws_send({"type": "file", "path": path, "content": new_content})
                self._diffs.append(FileDiff(path=path, diff=diff_str))
            if path not in self._files_changed:
                self._files_changed.append(path)
            return status

        return ToolExecutor([
            FunctionTool(_grep, name="grep"),
            FunctionTool(_glob, name="glob"),
            FunctionTool(_read_file, name="read_file"),
            FunctionTool(_write_file, name="write_file"),
            FunctionTool(_edit_file, name="edit_file"),
        ])

    def _llm_metadata(self, generation_name: str) -> dict:
        trace_id = self.trace_id or langfuse_context.get_current_trace_id()
        observation_id = langfuse_context.get_current_observation_id()
        return {
            "existing_trace_id": trace_id,
            "parent_observation_id": observation_id,
            "generation_name": generation_name,
        }

    @observe(name="followup-run")
    async def run(self, content: str) -> None:
        langfuse_context.update_current_observation(tags=["follow-up-agent"])

        await self.ws_send({"type": "phase", "phase": "exploring"})
        context = await self._build_context()

        history = await get_messages(self.project_id)
        messages = [
            Message(role=m.role, content=m.content)
            for m in history
            if not m.content.startswith(CARD_PREFIX)
        ]

        system_prompt = render_followup(
            project_summary=context["summary"],
            file_tree=context["file_tree"],
        )
        answer = await self._react_loop(messages, system_prompt)

        if answer:
            await self.ws_send({"type": "text", "content": answer})

        card = encode_card({
            "type": "followup_progress",
            "steps": self._steps,
            "answer": answer or None,
            "filesChanged": self._files_changed,
            "diffs": [{"path": d.path, "diff": d.diff} for d in self._diffs],
        })
        assistant_content = (answer + "\n" + card) if answer else card
        await save_message(self.project_id, "assistant", assistant_content)

        if self._diffs:
            await self.ws_send({
                "type": "followup_diffs",
                "diffs": [{"path": d.path, "diff": d.diff} for d in self._diffs],
            })

        await self.ws_send({"type": "phase", "phase": "complete"})
        await self.ws_send({"type": "action_complete"})

    @observe(name="followup-build-context")
    async def _build_context(self) -> dict:
        project = await get_project_by_session(self.session_id)
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

    @observe(name="followup-react-loop")
    async def _react_loop(self, messages: list[Message], system_prompt: str) -> str:
        working_messages: list[dict] = [m.to_dict() for m in messages]
        tool_schemas = self._executor.get_schemas()
        last_content = ""

        for self._iteration in range(MAX_ITERATIONS):
            response = await complete_chat_with_tools(
                messages=working_messages,
                system_prompt=system_prompt,
                tools=tool_schemas,
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

                step_data = {
                    "tool": tool_name,
                    "args": {k: v for k, v in args.items() if k != "content"},
                    "status": "running",
                    "iteration": self._iteration,
                }
                await self.ws_send({"type": "followup_step", **step_data})

                result = await self._executor.execute(tool_name, tool_use_id=tool_call.id, **args)
                result_str = str(result.value) if not result.is_error else f"Error: {result.value}"

                preview = result_str[:200] + "..." if len(result_str) > 200 else result_str
                step_data["status"] = "completed"
                step_data["result_preview"] = preview
                await self.ws_send({"type": "followup_step", **step_data})

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
                    "content": result_str,
                })

        logger.warning("[followup-agent] Hit max iterations (%d)", MAX_ITERATIONS)
        return last_content
