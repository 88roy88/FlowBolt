import json
import uuid
from typing import Any

from flow44.ai.agents._base import BaseAgent
from flow44.ai.agents.file_diffs import DiffTracker
from flow44.db.chat import ChatRole, save_message


class ChatAgent(BaseAgent):
    async def _save_response(
        self,
        answer: str,
        steps: list[dict[str, Any]],
    ) -> None:
        for step in steps:
            if step.get("type") == "assistant_turn":
                tools_label = ", ".join(tc["function"]["name"] for tc in step["raw_message"].get("tool_calls") or [])
                await save_message(self.project_id, ChatRole.assistant, tools_label, raw_message=step["raw_message"])
                continue

            preview = step.get("short_preview") or step.get("result_preview", "")
            result_short = preview[:80].replace("\n", " ").strip()
            if len(preview) > 80:
                result_short += "..."

            if step.get("raw_message") is not None:
                await save_message(self.project_id, ChatRole.tool, result_short, raw_message=step["raw_message"])
                continue

            # FixErrorAgent's synthetic pseudo-tool step
            tool = step.get("tool", "?")
            args = step.get("args", {})
            primary_arg = next((v for k, v in args.items() if k not in ("content",)), "")
            call_content = f"{tool} on {primary_arg!r}" if primary_arg else tool

            tool_call_id = str(uuid.uuid4())
            call_raw_message = {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {"name": tool, "arguments": json.dumps(args)},
                    }
                ],
            }
            result_raw_message = {"role": "tool", "tool_call_id": tool_call_id, "content": result_short}

            await save_message(self.project_id, ChatRole.assistant, call_content, raw_message=call_raw_message)
            await save_message(self.project_id, ChatRole.tool, result_short, raw_message=result_raw_message)

        if answer.strip():
            await save_message(self.project_id, ChatRole.assistant, answer)

    async def _write_file_and_emit_diff(self, tracker: DiffTracker, path: str, content: str) -> None:
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
        old_content = await self.sandbox.read_file(path)
        await self.sandbox.edit_file(path, search, replace)
        new_content = await self.sandbox.read_file(path)
        tracker.record(path, old_content, new_content, is_new=False)
        await self.emit({"type": "file", "path": path, "content": new_content})

    async def _emit_file_diffs_summary(self, tracker: DiffTracker) -> None:
        diffs = tracker.combined_diffs()
        if not diffs:
            return
        await self.emit(
            {
                "type": "file_diffs",
                "diffs": [{"path": d.path, "diff": d.diff, "is_new": d.is_new} for d in diffs],
            }
        )
