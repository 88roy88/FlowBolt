from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from langfuse.decorators import langfuse_context, observe

from flow44.ai.core.messages import Message
from flow44.ai.core.tools import FunctionTool, ToolExecutor
from flow44.ai.prompts import render_followup
from flow44.ai.provider import complete_chat_with_tools
from flow44.ai.tools.edit_file import edit_file_with_context
from flow44.ai.tools.glob import glob
from flow44.ai.tools.grep import grep
from flow44.ai.tools.read_file import read_file_with_lines
from flow44.ai.tools.write_file import write_file_with_diff
from flow44.models.chat import get_messages
from flow44.models.project import get_project
from flow44.sandbox.filesystem import list_files, read_file

from ._base import BaseAgent

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 15


@dataclass
class FileDiff:
    path: str
    diff: str


class FollowUpAgent(BaseAgent):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._steps: list[dict[str, Any]] = []
        self._diffs: list[FileDiff] = []
        self._files_changed: list[str] = []
        self._iteration = 0
        self._executor = self._build_tool_executor()

    def _build_tool_executor(self) -> ToolExecutor:
        sid = self.project_id

        # TODO: why we stopped supporting path?
        # TODO: we might want a better prompt for the llm to understand how to use grep patterns.
        # TODO: @roym: Think in general if there's a smart way to work with it like skills -
        #               and load the full instructions on how to use only if chose it
        async def _grep(pattern: str, file_pattern: str | None = None) -> str:
            """Search the entire codebase for a text or regex pattern using grep.

            Use this to find all occurrences of functions, classes, variables, imports, or any text pattern.
            Much faster than reading files one by one — always prefer this over glob+read for searching code.

            Args:
                pattern: Text or regex pattern to search for (e.g., "useState", "import.*axios", "className=")
                file_pattern: Optional file glob to narrow search (e.g., "*.tsx", "*.css")

            Returns:
                Matching lines with file paths and line numbers
            """
            return await grep(sid, pattern, "/", file_pattern)

        async def _glob(pattern: str) -> str:
            """Find files matching a glob pattern. Returns file paths."""
            return await glob(sid, pattern)

        async def _read_file(path: str) -> str:
            """Read the full content of a file with line numbers. Always read a file before editing it."""
            return await read_file_with_lines(sid, path)

        async def _write_file(path: str, content: str) -> str:
            """Write the full content of a file, creating it if needed. For small changes, prefer edit_file."""
            status, diff_str = await write_file_with_diff(sid, path, content)
            await self.emit({"type": "file", "path": path, "content": content})
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
                await self.emit({"type": "file", "path": path, "content": new_content})
                self._diffs.append(FileDiff(path=path, diff=diff_str))
            if path not in self._files_changed:
                self._files_changed.append(path)
            return status

        return ToolExecutor(
            [
                FunctionTool(_grep, name="grep"),
                FunctionTool(_glob, name="glob"),
                FunctionTool(_read_file, name="read_file"),
                FunctionTool(_write_file, name="write_file"),
                FunctionTool(_edit_file, name="edit_file"),
            ]
        )

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
        answer = await self._react_loop(messages, system_prompt)

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
            file_entries = await list_files(self.project_id)
            file_tree = self._format_file_tree(file_entries)
        except Exception:
            file_tree = "(unable to list files)"

        return {"summary": summary, "file_tree": file_tree}

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

    # TODO: switch here to use Flow? We can create a subclass of Flow ReActFlow  # noqa: E501
    # if needed something specific for general ReAct Flows.
    async def _react_loop(self, messages: list[Message], system_prompt: str) -> str:
        working_messages: list[dict[str, Any]] = [m.to_dict() for m in messages]
        tool_schemas = self._executor.get_schemas()
        last_content = ""

        # TODO: use my tricks of also sending warning messages when getting close or hitting max.
        # TODO: use max tools instead of max iterations? or maybe a combination of both?
        for self._iteration in range(MAX_ITERATIONS):
            response = await complete_chat_with_tools(
                messages=working_messages,  # type: ignore[arg-type]
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
                await self.emit({"type": "followup_step", **step_data})

                result = await self._executor.execute(tool_name, tool_use_id=tool_call.id, **args)
                result_str = str(result.value) if not result.is_error else f"Error: {result.value}"

                preview = result_str[:200] + "..." if len(result_str) > 200 else result_str
                step_data["status"] = "completed"
                step_data["result_preview"] = preview
                await self.emit({"type": "followup_step", **step_data})

                self._steps.append(
                    {
                        "id": str(uuid.uuid4()),
                        "tool": tool_name,
                        "args": {k: v for k, v in args.items() if k != "content"},
                        "status": "completed",
                        "resultPreview": preview,
                        "iteration": self._iteration,
                    }
                )

                working_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_str,
                    }
                )

        logger.warning("[followup-agent] Hit max iterations (%d)", MAX_ITERATIONS)
        return last_content

    # TODO: should we add a step to update the summary?
    # TODO: think about cases where the follow up is a big request that requires maybe recall the build agent.
