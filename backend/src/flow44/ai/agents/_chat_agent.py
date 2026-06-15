from typing import Any

from flow44.ai.agents._base import BaseAgent
from flow44.db.chat import ChatRole, save_message


class ChatAgent(BaseAgent):
    """Base for agents that participate in the chat history (followup, fix_error)."""

    async def _save_response(
        self,
        answer: str,
        steps: list[dict[str, Any]],
        files_changed: list[str],
    ) -> None:
        content = self._build_assistant_message(answer, steps, files_changed)
        if content.strip():
            await save_message(self.project_id, ChatRole.assistant, content)

    @staticmethod
    def _build_assistant_message(
        answer: str,
        steps: list[dict[str, Any]],
        files_changed: list[str],
    ) -> str:
        parts: list[str] = []

        action_lines: list[str] = []
        for step in steps:
            tool = step.get("tool", "?")
            args = step.get("args", {})
            preview = step.get("short_preview") or step.get("result_preview", "")
            primary_arg = next((v for k, v in args.items() if k not in ("content",)), "")
            result_short = preview[:80].replace("\n", " ").strip()
            if len(preview) > 80:
                result_short += "..."
            line = f"- {tool} on {primary_arg!r}" if primary_arg else f"- {tool}"
            if result_short:
                line += f": {result_short}"
            action_lines.append(line)
        if files_changed:
            action_lines.append(f"- files changed: {', '.join(files_changed)}")
        if action_lines:
            parts.append("Actions taken:\n" + "\n".join(action_lines))

        if answer:
            if parts:
                parts.append("")
            parts.append(answer)

        return "\n".join(parts)
