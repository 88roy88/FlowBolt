from __future__ import annotations

import logging
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)

from flow44.ai.core.provider import complete_chat_with_tools
from flow44.ai.core.tools import ToolExecutor, truncate_tool_args

logger = logging.getLogger(__name__)


def _truncate_tool_call_part(part: ToolCallPart) -> ToolCallPart:
    args = part.args_as_dict()
    return ToolCallPart(
        tool_name=part.tool_name,
        args=truncate_tool_args(args),
        tool_call_id=part.tool_call_id,
    )


class ReActFlow:
    def __init__(self, name: str = "react", max_iterations: int = 15) -> None:
        self.name = name
        self.max_iterations = max_iterations

    async def react_loop(
        self,
        messages: list[ModelMessage],
        system_prompt: str,
        tools: ToolExecutor,
        model_name: str | None = None,
        emit_fn: Any = None,
    ) -> str:
        tool_defs = tools.get_tool_definitions()

        working_messages: list[ModelMessage] = [
            ModelRequest(parts=[SystemPromptPart(content=system_prompt)]),
            *messages,
        ]
        last_content = ""

        for iteration in range(self.max_iterations):
            logger.info(
                "[react_loop:%s] Calling LLM | iteration=%d msgs=%d",
                self.name,
                iteration,
                len(working_messages),
            )

            try:
                response: ModelResponse = await complete_chat_with_tools(
                    working_messages,
                    system_prompt="",
                    tool_defs=tool_defs,
                    model_name=model_name,
                )
            except Exception:
                logger.exception("[react_loop:%s] LLM call failed | iteration=%d", self.name, iteration)
                raise

            text_parts = [p for p in response.parts if isinstance(p, TextPart)]
            tool_call_parts = [p for p in response.parts if isinstance(p, ToolCallPart)]
            last_content = " ".join(p.content for p in text_parts)

            if not tool_call_parts:
                return last_content

            working_messages.append(response)

            if emit_fn:
                truncated_parts = [
                    _truncate_tool_call_part(p) if isinstance(p, ToolCallPart) else p for p in response.parts
                ]
                await emit_fn({
                    "type": "react_assistant_turn",
                    "response": ModelResponse(parts=truncated_parts, usage=response.usage),
                    "iteration": iteration,
                })

            return_parts: list[ToolReturnPart] = []
            for tc in tool_call_parts:
                args = tc.args_as_dict()

                if emit_fn:
                    await emit_fn({
                        "type": "react_step",
                        "tool": tc.tool_name,
                        "args": {k: v for k, v in args.items() if k != "content"},
                        "status": "running",
                        "iteration": iteration,
                    })

                result = await tools.execute(tc.tool_name, tool_use_id=tc.tool_call_id, **args)
                result_str = str(result.value) if not result.is_error else f"Error: {result.value}"

                return_parts.append(
                    ToolReturnPart(tool_name=tc.tool_name, content=result_str, tool_call_id=tc.tool_call_id)
                )

                if emit_fn:
                    preview = result_str[:200] + "..." if len(result_str) > 200 else result_str
                    event: dict[str, object] = {
                        "type": "react_step",
                        "tool": tc.tool_name,
                        "args": {k: v for k, v in args.items() if k != "content"},
                        "status": "completed",
                        "result_preview": preview,
                        "iteration": iteration,
                        "tool_return": ToolReturnPart(
                            tool_name=tc.tool_name, content=preview, tool_call_id=tc.tool_call_id
                        ),
                    }
                    if result.short_preview:
                        event["short_preview"] = result.short_preview
                    await emit_fn(event)

            working_messages.append(ModelRequest(parts=return_parts))

        logger.warning("[%s] Hit max iterations (%d)", self.name, self.max_iterations)
        return last_content
