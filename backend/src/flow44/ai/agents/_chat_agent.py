import uuid
from typing import Any

from pydantic_ai.messages import (
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)

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
                response: ModelResponse = step["response"]
                tool_names = ", ".join(
                    p.tool_name for p in response.parts if isinstance(p, ToolCallPart)
                )
                serialized = ModelMessagesTypeAdapter.dump_json([response]).decode()
                await save_message(self.project_id, ChatRole.assistant, tool_names, raw_message=serialized)
                continue

            preview = step.get("short_preview") or step.get("result_preview", "")
            result_short = preview[:80].replace("\n", " ").strip()
            if len(preview) > 80:
                result_short += "..."

            if step.get("tool_return") is not None:
                tool_return: ToolReturnPart = step["tool_return"]
                serialized = ModelMessagesTypeAdapter.dump_json(
                    [ModelRequest(parts=[tool_return])]
                ).decode()
                await save_message(self.project_id, ChatRole.tool, result_short, raw_message=serialized)
                continue

            # FixErrorAgent's synthetic pseudo-tool step
            tool = step.get("tool", "?")
            args = step.get("args", {})
            primary_arg = next((v for k, v in args.items() if k not in ("content",)), "")
            call_content = f"{tool} on {primary_arg!r}" if primary_arg else tool

            tool_call_id = str(uuid.uuid4())
            call_response = ModelResponse(parts=[
                ToolCallPart(tool_name=tool, args=args, tool_call_id=tool_call_id)
            ])
            result_request = ModelRequest(parts=[
                ToolReturnPart(tool_name=tool, content=result_short, tool_call_id=tool_call_id)
            ])

            await save_message(
                self.project_id, ChatRole.assistant, call_content,
                raw_message=ModelMessagesTypeAdapter.dump_json([call_response]).decode(),
            )
            await save_message(
                self.project_id, ChatRole.tool, result_short,
                raw_message=ModelMessagesTypeAdapter.dump_json([result_request]).decode(),
            )

        if answer.strip():
            final = ModelResponse(parts=[TextPart(content=answer)])
            await save_message(
                self.project_id, ChatRole.assistant, answer,
                raw_message=ModelMessagesTypeAdapter.dump_json([final]).decode(),
            )

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
