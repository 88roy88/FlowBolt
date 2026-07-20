from typing import Any

from flow44.ai.agents._base import BaseAgent
from flow44.ai.agents.file_diffs import DiffTracker
from flow44.db.chat import ChatRole, save_message


class ChatAgent(BaseAgent):
    """Base for agents that participate in the chat history (followup, fix_error)."""

    async def _save_response(
        self,
        answer: str,
        steps: list[dict[str, Any]],
    ) -> None:
        """Persist the agent's turn to chat history: tool calls/results, and the final answer.

        When a step carries `raw_message` (from `ReActFlow`'s real assistant/tool messages), it's
        saved alongside the human-readable summary so history can be replayed as the literal
        conversation later, instead of a paraphrase. Steps without it (e.g. FixErrorAgent's
        synthetic pseudo-tool step, which never goes through `ReActFlow`) fall back to
        summary-only, as before.
        """
        for step in steps:
            if step.get("type") == "assistant_turn":
                # The real assistant message for this iteration (content + tool_calls, covering
                # every tool called in it) — the call side of every tool below is already fully
                # represented here, so per-tool steps only ever add a matching tool_result row.
                tools_label = ", ".join(tc["function"]["name"] for tc in step["raw_message"].get("tool_calls") or [])
                await save_message(self.project_id, ChatRole.tool_call, tools_label, raw_message=step["raw_message"])
                continue

            preview = step.get("short_preview") or step.get("result_preview", "")
            result_short = preview[:80].replace("\n", " ").strip()
            if len(preview) > 80:
                result_short += "..."

            if step.get("raw_message") is not None:
                # Came from ReActFlow: the matching assistant_turn row already recorded the call.
                await save_message(self.project_id, ChatRole.tool_result, result_short, raw_message=step["raw_message"])
                continue

            # FixErrorAgent's synthetic pseudo-tool step: no ReActFlow, no assistant_turn row.
            tool = step.get("tool", "?")
            args = step.get("args", {})
            primary_arg = next((v for k, v in args.items() if k not in ("content",)), "")
            call_content = f"{tool} on {primary_arg!r}" if primary_arg else tool
            await save_message(self.project_id, ChatRole.tool_call, call_content)
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
