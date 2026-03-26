import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from langfuse.decorators import langfuse_context, observe
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.usage import UsageLimits

from flow44.ai.prompts import render_followup
from flow44.ai.tools.edit_file import edit_file_with_context
from flow44.ai.tools.glob import glob as glob_tool
from flow44.ai.tools.grep import grep as grep_tool
from flow44.ai.tools.read_file import read_file_with_lines
from flow44.ai.tools.write_file import write_file_with_diff
from flow44.db.chat import get_messages
from flow44.db.project import get_project
from flow44.sandbox.main import PnpmSandbox

from ._base import BaseAgent

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 15


@dataclass
class FileDiff:
    path: str
    diff: str


@dataclass
class FollowUpDeps:
    sandbox: PnpmSandbox
    project_id: str
    emit: Callable[[dict[str, Any]], Awaitable[None]]
    diffs: list[FileDiff] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent & tools
# ---------------------------------------------------------------------------

followup_agent: Agent[FollowUpDeps, str] = Agent(deps_type=FollowUpDeps)


@followup_agent.tool
async def grep(ctx: RunContext[FollowUpDeps], pattern: str, file_pattern: str | None = None) -> str:
    """Search the entire codebase for a text or regex pattern using grep.

    Use this to find all occurrences of functions, classes, variables, imports, or any text pattern.
    Much faster than reading files one by one — always prefer this over glob+read for searching code.

    Args:
        pattern: Text or regex pattern to search for (e.g., "useState", "import.*axios", "className=")
        file_pattern: Optional file glob to narrow search (e.g., "*.tsx", "*.css")

    Returns:
        Matching lines with file paths and line numbers
    """
    args = {"pattern": pattern}
    if file_pattern:
        args["file_pattern"] = file_pattern
    await _emit_step(ctx, "grep", args, "running")
    result = await grep_tool(ctx.deps.sandbox, pattern, "/", file_pattern)
    await _emit_step(ctx, "grep", args, "completed", result)
    return result


@followup_agent.tool
async def glob(ctx: RunContext[FollowUpDeps], pattern: str) -> str:
    """Find files matching a glob pattern. Returns file paths."""
    await _emit_step(ctx, "glob", {"pattern": pattern}, "running")
    result = await glob_tool(ctx.deps.sandbox, pattern)
    await _emit_step(ctx, "glob", {"pattern": pattern}, "completed", result)
    return result


@followup_agent.tool
async def read_file(ctx: RunContext[FollowUpDeps], path: str) -> str:
    """Read the full content of a file with line numbers. Always read a file before editing it."""
    await _emit_step(ctx, "read_file", {"path": path}, "running")
    result = await read_file_with_lines(ctx.deps.sandbox, path)
    await _emit_step(ctx, "read_file", {"path": path}, "completed", result)
    return result


@followup_agent.tool
async def write_file(ctx: RunContext[FollowUpDeps], path: str, content: str) -> str:
    """Write the full content of a file, creating it if needed. For small changes, prefer edit_file."""
    await _emit_step(ctx, "write_file", {"path": path}, "running")
    status, diff_str = await write_file_with_diff(ctx.deps.sandbox, path, content)
    await ctx.deps.emit({"type": "file", "path": path, "content": content})
    if diff_str:
        ctx.deps.diffs.append(FileDiff(path=path, diff=diff_str))
    if path not in ctx.deps.files_changed:
        ctx.deps.files_changed.append(path)
    await _emit_step(ctx, "write_file", {"path": path}, "completed", status)
    return status


@followup_agent.tool
async def edit_file(ctx: RunContext[FollowUpDeps], path: str, search: str, replace: str) -> str:
    """Apply a targeted search-and-replace edit. The search string must match exactly."""
    await _emit_step(ctx, "edit_file", {"path": path, "search": search, "replace": replace}, "running")
    status, diff_str = await edit_file_with_context(ctx.deps.sandbox, path, search, replace)
    if diff_str:
        new_content = await ctx.deps.sandbox.read_file(path)
        await ctx.deps.emit({"type": "file", "path": path, "content": new_content})
        ctx.deps.diffs.append(FileDiff(path=path, diff=diff_str))
    if path not in ctx.deps.files_changed:
        ctx.deps.files_changed.append(path)
    await _emit_step(ctx, "edit_file", {"path": path}, "completed", status)
    return status


async def _emit_step(
    ctx: RunContext[FollowUpDeps],
    tool_name: str,
    args: dict[str, Any],
    status: str,
    result: str | None = None,
) -> None:
    step_data: dict[str, Any] = {
        "tool": tool_name,
        "args": args,
        "status": status,
        "iteration": len(ctx.deps.steps),
    }
    if result is not None:
        preview = result[:200] + "..." if len(result) > 200 else result
        step_data["result_preview"] = preview
    await ctx.deps.emit({"type": "followup_step", **step_data})

    if status == "completed":
        ctx.deps.steps.append(
            {
                "id": str(uuid.uuid4()),
                "tool": tool_name,
                "args": args,
                "status": "completed",
                "resultPreview": step_data.get("result_preview", ""),
                "iteration": step_data["iteration"],
            }
        )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


@followup_agent.system_prompt
async def _system_prompt(ctx: RunContext[FollowUpDeps]) -> str:
    context = await _build_context(ctx.deps.sandbox, ctx.deps.project_id)
    return render_followup(
        project_summary=context["summary"],
        file_tree=context["file_tree"],
    )


async def _build_context(sandbox: PnpmSandbox, project_id: str) -> dict[str, str]:
    project = await get_project(project_id)
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
        file_entries = await sandbox.list_files()
        file_tree = _format_file_tree(file_entries)
    except Exception:
        file_tree = "(unable to list files)"

    return {"summary": summary, "file_tree": file_tree}


def _format_file_tree(entries: list[Any], indent: int = 0) -> str:
    lines = []
    for entry in entries:
        prefix = "  " * indent
        if entry.is_directory:
            lines.append(f"{prefix}{entry.name}/")
            if entry.children:
                lines.append(_format_file_tree(entry.children, indent + 1))
        else:
            lines.append(f"{prefix}{entry.name}")
    return "\n".join(lines)


def _to_pydantic_ai_history(
    history: list[Any],
) -> list[ModelRequest | ModelResponse]:
    """Convert DB chat messages to pydantic-ai message format."""
    messages: list[ModelRequest | ModelResponse] = []
    for m in history:
        if m.role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=m.content)]))
        elif m.role == "assistant" and m.content.strip():
            messages.append(ModelResponse(parts=[TextPart(content=m.content)]))
    return messages


def _resolve_model(model: str | None) -> str | None:
    """Convert litellm model string to pydantic-ai format.

    litellm uses 'bedrock/model-name', pydantic-ai uses 'bedrock:model-name'.
    """
    if model is None:
        return None
    return model.replace("/", ":", 1)


# ---------------------------------------------------------------------------
# Agent class (thin wrapper for lifecycle & SSE)
# ---------------------------------------------------------------------------


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

    @observe(name="followup-agent-run")  # type: ignore[untyped-decorator]
    async def run(self, content: str) -> None:
        langfuse_context.update_current_observation(tags=["follow-up-agent"])

        await self.emit({"type": "phase", "phase": "exploring"})

        history = await get_messages(self.project_id)
        message_history = _to_pydantic_ai_history(history)

        deps = FollowUpDeps(
            sandbox=self.sandbox,
            project_id=self.project_id,
            emit=self.emit,
            diffs=self._diffs,
            files_changed=self._files_changed,
            steps=self._steps,
        )

        result = await followup_agent.run(
            content,
            deps=deps,
            message_history=message_history,
            model=_resolve_model(self.model),
            usage_limits=UsageLimits(request_limit=MAX_ITERATIONS),
        )

        answer = result.output
        if answer:
            await self.emit({"type": "text", "content": answer})

        if self._diffs:
            await self.emit(
                {
                    "type": "followup_diffs",
                    "diffs": [{"path": d.path, "diff": d.diff} for d in self._diffs],
                }
            )

        await self.emit({"type": "phase", "phase": "complete"})
        await self.emit({"type": "action_complete"})
