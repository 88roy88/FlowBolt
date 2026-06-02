"""Tests for AI helpers (JSON parsing, etc.)."""

from __future__ import annotations

from flow44.ai.helpers import parse_json_response


class TestParseJsonResponse:
    """Test JSON response parsing with various formats."""

    def test_valid_json(self) -> None:
        """Parse valid JSON."""
        result = parse_json_response('{"key": "value", "num": 42}')
        assert result == {"key": "value", "num": 42}

    def test_json_with_whitespace(self) -> None:
        """Parse JSON with leading/trailing whitespace."""
        result = parse_json_response('  \n{"key": "value"}  \n')
        assert result == {"key": "value"}

    def test_json_in_code_block(self) -> None:
        """Parse JSON wrapped in markdown code block."""
        result = parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_in_code_block_no_language(self) -> None:
        """Parse JSON wrapped in code block without language."""
        result = parse_json_response('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_with_text_before_and_after(self) -> None:
        """Extract JSON from text with surrounding content."""
        result = parse_json_response('Here is the result: {"key": "value"} done!')
        assert result == {"key": "value"}

    def test_nested_json(self) -> None:
        """Parse nested JSON structures."""
        json_str = '{"outer": {"inner": {"deep": "value"}}, "list": [1, 2, 3]}'
        result = parse_json_response(json_str)
        assert result["outer"]["inner"]["deep"] == "value"
        assert result["list"] == [1, 2, 3]

    def test_json_with_arrays(self) -> None:
        """Parse JSON with arrays."""
        result = parse_json_response('{"items": [{"id": 1}, {"id": 2}]}')
        assert len(result["items"]) == 2
        assert result["items"][0]["id"] == 1

    def test_invalid_json_returns_empty(self) -> None:
        """Invalid JSON returns empty dict."""
        result = parse_json_response("not json at all")
        assert result == {}

    def test_none_input_returns_empty(self) -> None:
        """None input returns empty dict."""
        result = parse_json_response(None)
        assert result == {}

    def test_empty_string_returns_empty(self) -> None:
        """Empty string returns empty dict."""
        result = parse_json_response("")
        assert result == {}

    def test_json_with_special_characters(self) -> None:
        """Parse JSON with special characters."""
        result = parse_json_response('{"text": "Line 1\\nLine 2\\tTabbed"}')
        assert "Line 1" in result["text"]
        assert "\\n" in result["text"] or "\n" in result["text"]

    def test_json_with_quotes(self) -> None:
        """Parse JSON with escaped quotes."""
        result = parse_json_response('{"message": "He said \\"hello\\""}')
        assert "hello" in result["message"]

    def test_multiple_json_objects_returns_empty(self) -> None:
        """When JSON has trailing text, current parser returns empty."""
        text = '{"first": 1} some text {"second": 2}'
        result = parse_json_response(text)
        # Parser can't handle multiple objects with text between them
        # This documents current behavior
        assert result == {}

    def test_json_with_trailing_comma(self) -> None:
        """Malformed JSON with trailing comma returns empty."""
        result = parse_json_response('{"key": "value",}')
        # This is invalid JSON, should return {}
        assert result == {}

    def test_unclosed_brace(self) -> None:
        """JSON with unclosed brace returns empty."""
        result = parse_json_response('{"key": "value"')
        assert result == {}

    def test_code_block_with_multiple_closing(self) -> None:
        """Handle code blocks with multiple ``` markers."""
        result = parse_json_response('```json\n{"key": "value"}\n```\n```')
        assert result == {"key": "value"}
