import asyncio
import difflib
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from langfuse.decorators import observe
from pydantic import BaseModel

from flow44.ai.agents._base import BaseAgent
from flow44.ai.agents.analyze_data_source import fetch_and_analyze_data_source, generate_data_source_files
from flow44.ai.agents.followup.prompts import render_followup
from flow44.ai.agents.optional_packages import allowed_import_names
from flow44.ai.core.messages import Message
from flow44.ai.core.react_flow import ReActFlow
from flow44.ai.core.tools import ToolExecutor, tool
from flow44.ai.generated_app_contract import (
    GeneratedAppContractError,
    validate_generated_app_file_contract,
    validate_generated_app_path_allowed,
)
from flow44.db.chat import get_messages
from flow44.db.project import get_project
from flow44.db.project_data_source import DataSourceContext, get_project_data_sources, update_project_data_sources
from flow44.sandbox.main import PnpmSandbox

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 15
MAX_READ_LINES = 1000


def _format_generated_app_contract_error(exc: GeneratedAppContractError) -> str:
    return (
        f"Generated app contract violation: {exc}\n"
        "Pick an editable app source file and only import packages selected for this project."
    )


@dataclass
class FileDiff:
    path: str
    diff: str
    is_new: bool = False


class FollowUpAgent(BaseAgent):
    def __init__(
        self,
        project_id: str,
        sandbox: PnpmSandbox,
        *,
        user_id: str,
        model: str | None = None,
        trace_id: str | None = None,
        data_source_authorization: str | None = None,
    ) -> None:
        super().__init__(project_id, sandbox, user_id, model=model, trace_id=trace_id)
        self._steps: list[dict[str, Any]] = []
        self._diffs: list[FileDiff] = []
        self._files_changed: list[str] = []
        self._iteration = 0
        self._selected_packages: list[str] = []
        self._data_source_authorization = data_source_authorization
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
        async def glob(pattern: str = "*") -> str:
            """Find files matching a glob pattern.

            Args: pattern: A glob pattern to match files (e.g., "*.tsx", "src/**/*.js"). Defaults to "*".

            Returns: A list of file paths matching the pattern, or a message if no files found.
            """
            results = await sandbox.glob(pattern)
            if not results:
                return "No files found matching pattern."
            return "\n".join(results)

        @tool
        async def read_file(path: str, offset: int = 0, limit: int = MAX_READ_LINES) -> str:
            """Read file content with line numbers. Always read a file before editing it.

            Args:
                path: File path to read.
                offset: Starting line number (0-based). Defaults to 0 (beginning of file).
                limit: Max number of lines to return. Defaults to 1000, max 1000.
            """
            try:
                content = await sandbox.read_file(path)
            except (FileNotFoundError, PermissionError) as e:
                return f"Error: {e}"
            lines = content.splitlines()
            total = len(lines)
            limit = min(limit, MAX_READ_LINES)
            chunk = lines[offset : offset + limit]
            numbered = [f"{i + offset + 1:4d} | {line}" for i, line in enumerate(chunk)]
            if offset + limit < total:
                numbered.append(f"\n... (showing lines {offset + 1}-{offset + len(chunk)}, file has {total} total)")
            return "\n".join(numbered)

        @tool
        async def write_file(path: str, content: str) -> str:
            """Write the full content of a file, creating it if needed. For small changes, prefer edit_file."""
            try:
                path = validate_generated_app_file_contract(
                    path, content, allowed_import_names(self._selected_packages)
                )
            except GeneratedAppContractError as exc:
                return _format_generated_app_contract_error(exc)
            try:
                old_content = await sandbox.read_file(path)
                is_new_file = False
            except FileNotFoundError:
                old_content = ""
                is_new_file = True
            await sandbox.write_file(path, content)
            await self._record_file_change(path, old_content, content, is_new=is_new_file)
            return f"OK — wrote {path} ({len(content.splitlines())} lines)"

        @tool
        async def edit_file(path: str, search: str, replace: str) -> str:
            """Apply a targeted search-and-replace edit. The search string must match exactly."""
            try:
                path = validate_generated_app_path_allowed(path)
            except GeneratedAppContractError as exc:
                return _format_generated_app_contract_error(exc)
            try:
                current = await sandbox.read_file(path)
            except FileNotFoundError:
                return f"Error: File not found: {path}"

            candidate = current.replace(search, replace, 1)
            try:
                path = validate_generated_app_file_contract(
                    path, candidate, allowed_import_names(self._selected_packages)
                )
            except GeneratedAppContractError as exc:
                return _format_generated_app_contract_error(exc)
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
            await self._record_file_change(path, current, new_content, is_new=False)
            return f"OK — edited {path}"

        return ToolExecutor([grep, glob, read_file, write_file, edit_file])

    async def _record_file_change(self, path: str, old_content: str, new_content: str, *, is_new: bool) -> None:
        diff_str = "".join(
            difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            )
        )
        await self.emit({"type": "file", "path": path, "content": new_content})
        if diff_str:
            self._diffs.append(FileDiff(path=path, diff=diff_str, is_new=is_new))
        if path not in self._files_changed:
            self._files_changed.append(path)

    @observe(name="followup-agent-run")  # type: ignore[untyped-decorator]
    async def run(self, content: str, data_source_ids: list[str] | None = None) -> None:
        self._setup_trace(["follow-up-agent"])

        new_data_source_contexts: list[DataSourceContext] = []
        existing_data_source_contexts: list[DataSourceContext] = []

        if data_source_ids:
            stored_contexts = await get_project_data_sources(self.project_id)
            stored_ids = {ds.data_source_id for ds in stored_contexts}
            await self.emit({"type": "phase", "phase": "fetching_data_sources"})
            try:
                updated_contexts: list[DataSourceContext] = list(
                    await asyncio.gather(*[self._fetch_analyze_and_write(sid, content) for sid in data_source_ids])
                )
            except Exception:
                await self.emit({"type": "error", "message": "Failed to fetch required data source data."})
                raise
            new_data_source_contexts = [ctx for ctx in updated_contexts if ctx.data_source_id not in stored_ids]
            existing_data_source_contexts = [ctx for ctx in updated_contexts if ctx.data_source_id in stored_ids]
            if updated_contexts:
                await self._persist_data_sources(updated_contexts, stored_contexts)

        await self.emit({"type": "phase", "phase": "exploring"})
        context = await self._build_context()
        try:
            self._selected_packages = await self._prepare_optional_packages()
        except Exception:
            await self.emit({"type": "error", "message": "Failed to install required packages."})
            raise

        history = await get_messages(self.project_id)
        messages = [
            Message(role=m.role, content=m.content)  # type: ignore[arg-type]
            for m in history
            if m.role == "user" or (m.role == "assistant" and m.content.strip())
        ]

        system_prompt = render_followup(
            project_summary=context["summary"],
            file_tree=context["file_tree"],
            selected_packages=self._selected_packages,
            new_data_source_contexts=new_data_source_contexts or None,
            existing_data_source_contexts=existing_data_source_contexts or None,
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
                    "diffs": [{"path": d.path, "diff": d.diff, "is_new": d.is_new} for d in self._diffs],
                }
            )

        # TODO: do we need both events?
        await self.emit({"type": "phase", "phase": "complete"})
        await self.emit({"type": "action_complete"})

    async def _fetch_analyze_and_write(self, sid: str, user_content: str) -> DataSourceContext:
        ctx = await fetch_and_analyze_data_source(
            sid,
            user_content,
            self._data_source_authorization,
            self.model,
            self._llm_metadata,
        )
        await self._write_data_source_module(ctx)
        return ctx

    async def _write_data_source_module(self, ctx: DataSourceContext) -> None:
        files = generate_data_source_files(ctx)
        module_path = next(iter(files))
        content = files[module_path]
        ctx.module_path = module_path

        try:
            old_content = await self.sandbox.read_file(module_path)
            is_new_module = False
        except FileNotFoundError:
            old_content = ""
            is_new_module = True

        await self.sandbox.write_file(module_path, content)
        await self._record_file_change(module_path, old_content, content, is_new=is_new_module)

    async def _persist_data_sources(
        self, updated_contexts: list[DataSourceContext], stored: list[DataSourceContext]
    ) -> None:
        by_id: dict[tuple[str, str], DataSourceContext] = {(ds.type, ds.data_source_id): ds for ds in stored}
        for ctx in updated_contexts:
            by_id[(ctx.type, ctx.data_source_id)] = ctx
        await update_project_data_sources(self.project_id, list(by_id.values()))

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
