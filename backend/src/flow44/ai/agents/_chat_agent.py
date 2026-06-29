from typing import Any

from flow44.ai.agents._base import BaseAgent
from flow44.db.chat import ChatRole, save_message


class ChatAgent(BaseAgent):
    """Base for agents that participate in the chat history (followup, fix_error)."""

    async def _save_response(
        self,
        answer: str,
        steps: list[dict[str, Any]],
    ) -> None:
        for step in steps:
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
