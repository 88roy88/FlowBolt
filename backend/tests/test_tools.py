"""Tests for the tool framework — schema generation, execution, error handling."""

from __future__ import annotations

import pytest

from flow44.ai.core.tools import FunctionTool, ToolExecutor


class TestFunctionToolSchema:
    def test_schema_from_simple_function(self) -> None:
        async def greet(name: str) -> str:
            """Say hello to someone."""
            return f"Hello, {name}!"

        tool = FunctionTool(greet, name="greet")
        schema = tool.schema

        assert schema.name == "greet"
        assert schema.description == "Say hello to someone."
        assert "name" in schema.input_schema["properties"]
        assert schema.input_schema["required"] == ["name"]

    def test_schema_with_optional_params(self) -> None:
        async def search(pattern: str, path: str = "/", max_results: int = 50) -> str:
            """Search for files."""
            return ""

        tool = FunctionTool(search, name="search")
        schema = tool.schema

        assert schema.input_schema["required"] == ["pattern"]
        assert "path" in schema.input_schema["properties"]
        assert "max_results" in schema.input_schema["properties"]

    def test_schema_with_optional_type(self) -> None:
        async def read(path: str, encoding: str | None = None) -> str:
            return ""

        tool = FunctionTool(read, name="read")
        schema = tool.schema

        assert schema.input_schema["required"] == ["path"]

    def test_custom_name_and_description(self) -> None:
        async def fn(x: int) -> int:
            return x

        tool = FunctionTool(fn, name="my_tool", description="Custom desc")
        assert tool.schema.name == "my_tool"
        assert tool.schema.description == "Custom desc"

    def test_to_litellm_dict(self) -> None:
        async def fn(x: str) -> str:
            """Do stuff."""
            return x

        tool = FunctionTool(fn, name="test")
        d = tool.schema.to_litellm_dict()

        assert d["type"] == "function"
        assert d["function"]["name"] == "test"
        assert d["function"]["description"] == "Do stuff."
        assert "parameters" in d["function"]


class TestFunctionToolExecution:
    @pytest.mark.asyncio
    async def test_successful_execution(self) -> None:
        async def add(a: int, b: int) -> int:
            return a + b

        tool = FunctionTool(add, name="add")
        result = await tool.execute(a=3, b=4)

        assert result.value == 7
        assert result.is_error is False
        assert result.tool_name == "add"

    @pytest.mark.asyncio
    async def test_sync_function_works(self) -> None:
        def multiply(a: int, b: int) -> int:
            return a * b

        tool = FunctionTool(multiply, name="multiply")
        result = await tool.execute(a=3, b=4)

        assert result.value == 12
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_exception_returns_error_result(self) -> None:
        async def fail(x: str) -> str:
            msg = "Something went wrong"
            raise ValueError(msg)

        tool = FunctionTool(fail, name="fail")
        result = await tool.execute(x="test")

        assert result.is_error is True
        assert "Something went wrong" in str(result.value)


class TestToolExecutor:
    @pytest.mark.asyncio
    async def test_dispatch_to_correct_tool(self) -> None:
        async def tool_a() -> str:
            return "a"

        async def tool_b() -> str:
            return "b"

        executor = ToolExecutor([
            FunctionTool(tool_a, name="a"),
            FunctionTool(tool_b, name="b"),
        ])

        result = await executor.execute("b")
        assert result.value == "b"

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self) -> None:
        executor = ToolExecutor([])
        result = await executor.execute("nonexistent")

        assert result.is_error is True
        assert "Unknown tool" in str(result.value)

    def test_get_schemas(self) -> None:
        async def greet(name: str) -> str:
            """Say hello."""
            return f"Hello {name}"

        executor = ToolExecutor([FunctionTool(greet, name="greet")])
        schemas = executor.get_schemas()

        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "greet"
