"""Tests for build error parser — pattern matching, ignore filters, parsing."""

from __future__ import annotations

from flow44.errors.parser import (
    BuildError,
    is_error_line,
    parse_error_block,
    should_ignore,
    strip_ansi,
)


# Helper to match old to_dict behavior
def _dump(err: BuildError) -> dict:
    return err.model_dump(exclude_none=True)


class TestStripAnsi:
    def test_removes_color_codes(self) -> None:
        assert strip_ansi("\x1b[31mERROR\x1b[0m") == "ERROR"

    def test_plain_text_unchanged(self) -> None:
        assert strip_ansi("hello world") == "hello world"


class TestShouldIgnore:
    def test_npm_notice(self) -> None:
        assert should_ignore("npm notice New minor version of npm available!")

    def test_npm_warn(self) -> None:
        assert should_ignore("npm warn some warning here")

    def test_update_available(self) -> None:
        assert should_ignore("   Update available! 10.6.5 → 10.32.1")

    def test_corepack(self) -> None:
        assert should_ignore("Corepack is about to download https://registry.npmjs.org/pnpm")

    def test_pnpm_approve(self) -> None:
        assert should_ignore('Run "pnpm approve-builds" to pick which dependencies')

    def test_real_error_not_ignored(self) -> None:
        assert not should_ignore("src/App.tsx(12,5): error TS2304: Cannot find name 'foo'")

    def test_empty_line(self) -> None:
        assert not should_ignore("")


class TestIsErrorLine:
    def test_vite_error(self) -> None:
        assert is_error_line("[vite] Internal server error: ...")

    def test_ts_error(self) -> None:
        assert is_error_line("src/App.tsx(12,5): error TS2304: Cannot find name 'foo'")

    def test_file_line_col_with_error(self) -> None:
        assert is_error_line("error /home/user/project/src/App.tsx:12:5")

    def test_normal_log_line(self) -> None:
        assert not is_error_line("VITE v5.0.0  ready in 200ms")

    def test_empty(self) -> None:
        assert not is_error_line("")


class TestParseErrorBlock:
    def test_typescript_error(self) -> None:
        block = "src/App.tsx(12,5): error TS2304: Cannot find name 'foo'"
        result = parse_error_block(block)
        assert result is not None
        assert result.file == "src/App.tsx"
        assert result.line == 12
        assert result.column == 5
        assert "foo" in result.message

    def test_file_line_col_error(self) -> None:
        block = "Something went wrong\n/home/user/project/src/App.tsx:42:10\nDetails here"
        result = parse_error_block(block)
        assert result is not None
        assert result.file == "/home/user/project/src/App.tsx"
        assert result.line == 42

    def test_vite_internal_server_error(self) -> None:
        block = (
            "[vite] Internal server error: /home/project/src/App.tsx: Missing initializer in const declaration. (38:13)"
        )
        result = parse_error_block(block)
        assert result is not None
        assert result.file == "/home/project/src/App.tsx"
        assert result.line == 38
        assert result.column == 13
        assert "Missing initializer" in result.message

    def test_vite_error_in_node_modules_no_file(self) -> None:
        block = "[vite] Internal server error: /home/project/node_modules/@babel/parser/lib/index.js: Unexpected token (42:8)"
        result = parse_error_block(block)
        assert result is not None
        assert result.file is None
        assert result.line is None
        assert "Unexpected token" in result.message

    def test_node_modules_file_line_col_ignored(self) -> None:
        block = "Error\n/home/project/node_modules/.pnpm/@babel+parser@7.29.2/node_modules/@babel/parser/lib/index.js:11066:23"
        result = parse_error_block(block)
        assert result is not None
        assert result.file is None

    def test_generic_fallback(self) -> None:
        block = "ERROR: Build failed miserably"
        result = parse_error_block(block)
        assert result is not None
        assert "Build failed" in result.message
        assert result.file is None

    def test_dedup_by_file_and_line(self) -> None:
        err1 = BuildError(message="Pre-transform error", file="src/App.tsx", line=38)
        err2 = BuildError(message="Internal server error", file="src/App.tsx", line=38)
        err3 = BuildError(message="oops", file="src/App.tsx", line=99)
        assert err1 == err2  # same file+line, different message
        assert hash(err1) == hash(err2)
        assert err1 != err3  # different line
        assert {err1, err2} == {err1}

    def test_model_dump_minimal(self) -> None:
        err = BuildError(message="oops")
        d = _dump(err)
        assert d == {"source": "build", "message": "oops"}
        assert "file" not in d

    def test_model_dump_full(self) -> None:
        err = BuildError(message="oops", file="a.ts", line=1, column=2)
        d = _dump(err)
        assert d["file"] == "a.ts"
        assert d["line"] == 1
        assert d["column"] == 2
