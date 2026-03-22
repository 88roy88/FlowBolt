from __future__ import annotations

import inspect
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from functools import wraps
from typing import Any, TypeVar, get_type_hints, overload

from pydantic import TypeAdapter

logger = logging.getLogger(__name__)


class ToolError(Exception):
    pass


class ToolResult:
    def __init__(
        self,
        value: Any,
        tool_use_id: str | None = None,
        tool_name: str | None = None,
        is_error: bool = False,
    ):
        self.value = value
        self.tool_use_id = tool_use_id
        self.tool_name = tool_name
        self.is_error = is_error

    def __str__(self) -> str:
        return str(self.value)


class ToolSchema:
    def __init__(self, name: str, description: str, input_schema: dict[str, Any]) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_litellm_dict(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class Tool(ABC):
    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        pass

    @property
    @abstractmethod
    def schema(self) -> ToolSchema:
        pass


class FunctionTool(Tool):
    def __init__(
        self,
        func: Callable[..., Any],
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        self._func = func
        self._name = name or func.__name__
        self._description = description or (inspect.getdoc(func) or "").strip()
        self._schema = self._build_schema()

    def _build_schema(self) -> ToolSchema:
        sig = inspect.signature(self._func)
        hints = get_type_hints(self._func)

        properties: dict[str, Any] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "return"):
                continue
            param_type = hints.get(param_name, Any)
            properties[param_name] = TypeAdapter(param_type).json_schema()
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        input_schema = {"type": "object", "properties": properties, "required": required}
        return ToolSchema(name=self._name, description=self._description, input_schema=input_schema)

    @property
    def schema(self) -> ToolSchema:
        return self._schema

    async def execute(self, tool_use_id: str | None = None, **kwargs: Any) -> ToolResult:
        try:
            result = self._func(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            return ToolResult(value=result, is_error=False, tool_use_id=tool_use_id, tool_name=self._name)
        except Exception as e:
            logger.exception("Tool '%s' failed", self._name)
            return ToolResult(value=str(e), is_error=True, tool_use_id=tool_use_id, tool_name=self._name)


F = TypeVar("F", bound=Callable[..., Any])


@overload
def tool(func: F, *, name: str | None = None, description: str | None = None) -> FunctionTool: ...


@overload
def tool(*, name: str | None = None, description: str | None = None) -> Callable[[F], FunctionTool]: ...


def tool(
    func: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> FunctionTool | Callable[[Callable[..., Any]], FunctionTool]:
    def decorator(f: Callable[..., Any]) -> FunctionTool:
        @wraps(f)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            return f(*args, **kwargs)

        return FunctionTool(wrapped, name=name, description=description)

    return decorator if func is None else decorator(func)


class ToolExecutor:
    def __init__(self, tools: Sequence[Tool]) -> None:
        self._tools = {t.schema.name: t for t in tools}

    def get_schemas(self) -> list[dict[str, Any]]:
        return [t.schema.to_litellm_dict() for t in self._tools.values()]

    async def execute(self, tool_name: str, tool_use_id: str | None = None, **kwargs: Any) -> ToolResult:
        t = self._tools.get(tool_name)
        if not t:
            return ToolResult(
                value=f"Unknown tool: {tool_name}",
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                is_error=True,
            )
        return await t.execute(tool_use_id=tool_use_id, **kwargs)

# TODO: bring the parallel tool execution from `/Users/roymezan/src/primesrc/code-validation-service/src/service/ai_logic`
