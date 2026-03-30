"""ReActFlow: Flow subclass for Reason + Act agents with tool loops."""

from __future__ import annotations

import json
import logging
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from flow44.ai.core.flow import Flow
from flow44.ai.core.messages import Message
from flow44.ai.core.provider import complete_chat_with_tools
from flow44.ai.core.tools import ToolExecutor

logger = logging.getLogger(__name__)

StateT = TypeVar("StateT", bound=BaseModel)


class ReActFlow(Flow[StateT], Generic[StateT]):
    """
    Flow subclass for ReAct (Reason + Act) pattern with tool usage.

    Implements the standard ReAct loop:
    1. Call LLM with tools available
    2. If no tool calls → return answer (flow ends)
    3. If tool calls → execute tools, add results to messages, loop back to step 1

    Automatically handles:
    - Tool execution
    - Message history management
    - Max iteration limits
    - Error handling
    """

    def __init__(
        self,
        name: str = "react",
        max_iterations: int = 15,
    ) -> None:
        super().__init__(name)
        self.max_iterations = max_iterations

    async def react_loop(
        self,
        messages: list[Message],
        system_prompt: str,
        tools: ToolExecutor,
        model: str | None = None,
        metadata_fn: Any = None,
        emit_fn: Any = None,
    ) -> str:
        """
        Run the ReAct loop: LLM → tools → LLM → tools → ... until done.

        Args:
            messages: Conversation history
            system_prompt: System prompt for the LLM
            tools: ToolExecutor with available tools
            model: Model to use
            metadata_fn: Optional function to generate metadata for observability
            emit_fn: Optional function to emit progress events

        Returns:
            Final assistant response (when no tool calls remain)
        """
        working_messages: list[dict[str, Any]] = [m.to_dict() for m in messages]
        tool_schemas = tools.get_schemas()
        last_content = ""

        for iteration in range(self.max_iterations):
            # Call LLM with tools
            metadata = metadata_fn(f"react-{iteration}") if metadata_fn else None
            response = await complete_chat_with_tools(
                messages=working_messages,  # type: ignore[arg-type]
                system_prompt=system_prompt,
                tools=tool_schemas,
                model=model,
                metadata=metadata,
            )

            choice = response.choices[0]
            message = choice.message
            last_content = message.content or ""

            # No tool calls → we're done
            if not message.tool_calls:
                return last_content

            # Add assistant message with tool calls
            working_messages.append(message.model_dump())

            # Execute each tool call
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                # Emit progress if callback provided
                if emit_fn:
                    step_data = {
                        "tool": tool_name,
                        "args": {k: v for k, v in args.items() if k != "content"},
                        "status": "running",
                        "iteration": iteration,
                    }
                    await emit_fn({"type": "react_step", **step_data})

                # Execute tool
                result = await tools.execute(tool_name, tool_use_id=tool_call.id, **args)
                result_str = str(result.value) if not result.is_error else f"Error: {result.value}"

                # Emit completion if callback provided
                if emit_fn:
                    preview = result_str[:200] + "..." if len(result_str) > 200 else result_str
                    await emit_fn(
                        {
                            "type": "react_step",
                            "tool": tool_name,
                            "status": "completed",
                            "result_preview": preview,
                            "iteration": iteration,
                        }
                    )

                # Add tool result to messages
                working_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_str,
                    }
                )

        logger.warning("[%s] Hit max iterations (%d)", self.name, self.max_iterations)
        return last_content
