from __future__ import annotations

import json
import logging
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from flow44.ai.core.flow import Flow
from flow44.ai.core.messages import Message
from flow44.ai.core.provider import complete_chat_with_tools
from flow44.ai.core.tools import ToolExecutor, truncate_tool_args

logger = logging.getLogger(__name__)

StateT = TypeVar("StateT", bound=BaseModel)


class ReActFlow(Flow[StateT], Generic[StateT]):
    def __init__(
        self,
        name: str = "react",
        max_iterations: int = 15,
    ) -> None:
        super().__init__(name)
        self.max_iterations = max_iterations

    async def react_loop(
        self,
        messages: list[dict[str, Any] | Message],
        system_prompt: str,
        tools: ToolExecutor,
        model: str | None = None,
        metadata_fn: Any = None,
        emit_fn: Any = None,
    ) -> str:
        working_messages: list[dict[str, Any]] = [m.to_dict() if isinstance(m, Message) else m for m in messages]
        tool_schemas = tools.get_schemas()
        last_content = ""

        for iteration in range(self.max_iterations):
            metadata = (
                metadata_fn(f"react-{iteration}", extra_metadata={"available_tools": tool_schemas})
                if metadata_fn
                else None
            )

            try:
                logger.info(
                    "[react_loop:%s] Calling LLM | iteration=%d msgs=%d",
                    self.name,
                    iteration,
                    len(working_messages),
                )
                response = await complete_chat_with_tools(
                    messages=working_messages,  # type: ignore[arg-type]
                    system_prompt=system_prompt,
                    tools=tool_schemas,
                    model=model,
                    metadata=metadata,
                )
            except Exception:
                logger.exception(
                    "[react_loop:%s] LLM call failed | iteration=%d msgs=%d last_role=%s",
                    self.name,
                    iteration,
                    len(working_messages),
                    working_messages[-1].get("role") if working_messages else "none",
                )
                raise

            choice = response.choices[0]
            message = choice.message
            last_content = message.content or ""

            if not message.tool_calls:
                return last_content

            assistant_message = message.model_dump()
            working_messages.append(assistant_message)

            raw_assistant_message = dict(assistant_message)
            raw_assistant_message["tool_calls"] = [
                {
                    **tc,
                    "function": {
                        **tc["function"],
                        "arguments": json.dumps(truncate_tool_args(json.loads(tc["function"]["arguments"] or "{}"))),
                    },
                }
                for tc in assistant_message.get("tool_calls") or []
            ]
            if emit_fn:
                await emit_fn(
                    {
                        "type": "react_assistant_turn",
                        "raw_message": raw_assistant_message,
                        "iteration": iteration,
                    }
                )

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                if emit_fn:
                    step_data = {
                        "tool": tool_name,
                        "args": {k: v for k, v in args.items() if k != "content"},
                        "status": "running",
                        "iteration": iteration,
                    }
                    await emit_fn({"type": "react_step", **step_data})

                result = await tools.execute(tool_name, tool_use_id=tool_call.id, **args)
                result_str = str(result.value) if not result.is_error else f"Error: {result.value}"

                if emit_fn:
                    preview = result_str[:200] + "..." if len(result_str) > 200 else result_str
                    event: dict[str, object] = {
                        "type": "react_step",
                        "tool": tool_name,
                        "args": {k: v for k, v in args.items() if k != "content"},
                        "status": "completed",
                        "result_preview": preview,
                        "iteration": iteration,
                        "raw_message": {"role": "tool", "tool_call_id": tool_call.id, "content": preview},
                    }
                    if result.short_preview:
                        event["short_preview"] = result.short_preview
                    await emit_fn(event)

                working_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_str,
                    }
                )

        logger.warning("[%s] Hit max iterations (%d)", self.name, self.max_iterations)
        return last_content
