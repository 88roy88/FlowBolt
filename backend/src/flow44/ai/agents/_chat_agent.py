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

        if steps:
            for step in steps:
                tool = step.get("tool", "?")
                args = step.get("args", {})
                preview = step.get("resultPreview", "")

                args_str = " ".join(
                    f"{k}={v!r}" if not isinstance(v, str) else f"{k}={v}"
                    for k, v in args.items()
                    if k != "content"
                )
                result_short = preview[:80].replace("\n", " ").strip()
                if len(preview) > 80:
                    result_short += "..."

                line = f"[{tool}: {args_str}".rstrip()
                if result_short:
                    line += f" → {result_short}"
                line += "]"
                parts.append(line)

        if files_changed:
            parts.append(f"[Changed: {', '.join(files_changed)}]")

        if answer:
            if parts:
                parts.append("")
            parts.append(answer)

        return "\n".join(parts)
