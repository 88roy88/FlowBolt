"""Tests for LLM response parsing helpers."""

from __future__ import annotations

from flow44.ai.helpers import parse_json_response


class TestParseJsonResponse:
    def test_clean_json(self) -> None:
        result = parse_json_response('{"key": "value", "num": 42}')
        assert result == {"key": "value", "num": 42}

    def test_json_with_markdown_fences(self) -> None:
        result = parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_with_bare_fences(self) -> None:
        result = parse_json_response('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_with_surrounding_text(self) -> None:
        """LLM sometimes wraps JSON in explanation text."""
        result = parse_json_response(
            'Here is the architecture:\n{"components": []}  \nLet me know if you need changes.'
        )
        assert result == {"components": []}

    def test_none_input(self) -> None:
        result = parse_json_response(None)
        assert result == {}

    def test_empty_string(self) -> None:
        result = parse_json_response("")
        assert result == {}

    def test_completely_invalid(self) -> None:
        result = parse_json_response("this is not json at all")
        assert result == {}

    def test_nested_json(self) -> None:
        result = parse_json_response('{"features": [{"title": "Todo", "desc": "A todo app"}]}')
        assert len(result["features"]) == 1
        assert result["features"][0]["title"] == "Todo"

    def test_json_with_newlines_in_values(self) -> None:
        result = parse_json_response('{"summary": "line1\\nline2"}')
        assert "line1" in result["summary"]

    def test_json_with_trailing_comma_fails_gracefully(self) -> None:
        """JSON with trailing comma is invalid — should use fallback extraction."""
        result = parse_json_response('{"key": "value",}')
        # Fallback extraction finds the outermost { }
        # This may or may not parse depending on the fallback — just shouldn't crash
        assert isinstance(result, dict)
