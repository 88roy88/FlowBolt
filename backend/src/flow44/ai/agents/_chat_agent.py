import json
import logging
from typing import Any

from flow44.ai.agents._base import BaseAgent
from flow44.ai.agents.file_diffs import DiffTracker
from flow44.ai.agents.optional_packages import installed_packages
from flow44.db.chat import ChatRole, save_message

logger = logging.getLogger(__name__)


class ChatAgent(BaseAgent):
    """Base for agents that participate in the chat history (followup, fix_error)."""

    async def _installed_optional_package_names(self) -> list[str]:
        try:
            manifest = json.loads(await self.sandbox.read_file("package.json"))
            deps = {**manifest.get("dependencies", {}), **manifest.get("devDependencies", {})}
        except (OSError, ValueError, AttributeError, TypeError):
            logger.warning("[chat-agent] Could not read package.json for %s", self.project_id)
            return []
        return [pkg.name for pkg in installed_packages(deps)]

    async def _save_response(
        self,
        answer: str,
        steps: list[dict[str, Any]],
    ) -> None:
        """Persist the agent's turn to chat history: reasoning, tool calls/results, and the final answer."""
        for step in steps:
            if step.get("type") == "reasoning":
                await save_message(self.project_id, ChatRole.reasoning, step["content"])
                continue

            tool = step.get("tool", "?")
            args = step.get("args", {})
            primary_arg = next((v for k, v in args.items() if k not in ("content",)), "")
            call_content = f"{tool} on {primary_arg!r}" if primary_arg else tool
            await save_message(self.project_id, ChatRole.tool_call, call_content)

            preview = step.get("short_preview") or step.get("result_preview", "")
            result_short = preview[:80].replace("\n", " ").strip()
            if len(preview) > 80:
                result_short += "..."
            await save_message(self.project_id, ChatRole.tool_result, result_short)

        if answer.strip():
            await save_message(self.project_id, ChatRole.assistant, answer)

    async def _write_file_and_emit_diff(self, tracker: DiffTracker, path: str, content: str) -> None:
        """Write a file to the sandbox, emit a live `file` event, and record the change in the tracker."""
        try:
            old_content = await self.sandbox.read_file(path)
            is_new = False
        except FileNotFoundError:
            old_content = ""
            is_new = True
        await self.sandbox.write_file(path, content)
        tracker.record(path, old_content, content, is_new=is_new)
        await self.emit({"type": "file", "path": path, "content": content})

    async def _edit_file_and_emit_diff(self, tracker: DiffTracker, path: str, search: str, replace: str) -> None:
        """Apply a search-and-replace edit in the sandbox, emit a live `file` event, and record the change.

        Raises `FileNotFoundError` if the file doesn't exist and `ValueError` if `search` doesn't match.
        """
        old_content = await self.sandbox.read_file(path)
        await self.sandbox.edit_file(path, search, replace)
        new_content = await self.sandbox.read_file(path)
        tracker.record(path, old_content, new_content, is_new=False)
        await self.emit({"type": "file", "path": path, "content": new_content})

    async def _emit_file_diffs_summary(self, tracker: DiffTracker) -> None:
        """Emit a single `file_diffs` event with one combined diff per file changed during the run."""
        diffs = tracker.combined_diffs()
        if not diffs:
            return
        await self.emit(
            {
                "type": "file_diffs",
                "diffs": [{"path": d.path, "diff": d.diff, "is_new": d.is_new} for d in diffs],
            }
        )
