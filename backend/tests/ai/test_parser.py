"""Tests for the flowArtifact XML streaming parser."""

from __future__ import annotations

from flow44.ai.parser import ActionParser


class TestActionParserBasic:
    def test_single_file(self) -> None:
        files: list[tuple[str, str]] = []
        parser = ActionParser(on_file_action=lambda p, c: files.append((p, c)))

        parser.feed(
            '<flowArtifact id="test" title="test">'
            '<flowAction type="file" filePath="src/App.tsx">'
            "export default function App() { return <div /> }"
            "</flowAction>"
            "</flowArtifact>"
        )
        parser.flush()

        assert len(files) == 1
        assert files[0][0] == "src/App.tsx"
        assert "App()" in files[0][1]

    def test_multiple_files(self) -> None:
        files: list[tuple[str, str]] = []
        parser = ActionParser(on_file_action=lambda p, c: files.append((p, c)))

        parser.feed(
            '<flowArtifact id="test" title="test">'
            '<flowAction type="file" filePath="src/types.ts">'
            "export interface Todo { id: string; text: string }"
            "</flowAction>"
            '<flowAction type="file" filePath="src/App.tsx">'
            "import { Todo } from './types'"
            "</flowAction>"
            "</flowArtifact>"
        )
        parser.flush()

        assert len(files) == 2
        assert files[0][0] == "src/types.ts"
        assert files[1][0] == "src/App.tsx"

    def test_text_before_and_after_artifact(self) -> None:
        texts: list[str] = []
        files: list[tuple[str, str]] = []
        parser = ActionParser(
            on_text=lambda t: texts.append(t),
            on_file_action=lambda p, c: files.append((p, c)),
        )

        parser.feed(
            "Here is the code:\n"
            '<flowArtifact id="test" title="test">'
            '<flowAction type="file" filePath="app.ts">'
            "const x = 1"
            "</flowAction>"
            "</flowArtifact>"
            "\nDone!"
        )
        parser.flush()

        assert len(files) == 1
        joined_text = "".join(texts)
        assert "Here is the code:" in joined_text
        assert "Done!" in joined_text

    def test_empty_file_content(self) -> None:
        files: list[tuple[str, str]] = []
        parser = ActionParser(on_file_action=lambda p, c: files.append((p, c)))

        parser.feed(
            '<flowArtifact id="test" title="test">'
            '<flowAction type="file" filePath="empty.ts">'
            "</flowAction>"
            "</flowArtifact>"
        )
        parser.flush()

        assert len(files) == 1
        assert files[0][0] == "empty.ts"
        assert files[0][1] == ""


class TestActionParserStreaming:
    def test_chunked_input(self) -> None:
        """Parser should handle input arriving in small chunks."""
        files: list[tuple[str, str]] = []
        parser = ActionParser(on_file_action=lambda p, c: files.append((p, c)))

        # Feed one character at a time
        full = (
            '<flowArtifact id="test" title="test">'
            '<flowAction type="file" filePath="src/App.tsx">'
            "const x = 42"
            "</flowAction>"
            "</flowArtifact>"
        )
        for char in full:
            parser.feed(char)
        parser.flush()

        assert len(files) == 1
        assert files[0][1] == "const x = 42"

    def test_split_across_tags(self) -> None:
        """Parser should handle tag boundaries split across chunks."""
        files: list[tuple[str, str]] = []
        parser = ActionParser(on_file_action=lambda p, c: files.append((p, c)))

        parser.feed('<flowArtifact id="test" title="te')
        parser.feed('st"><flowAction type="file" file')
        parser.feed('Path="app.ts">hello world</flow')
        parser.feed("Action></flowArtifact>")
        parser.flush()

        assert len(files) == 1
        assert files[0][1] == "hello world"

    def test_no_artifact(self) -> None:
        """Plain text with no artifact should just emit text."""
        texts: list[str] = []
        files: list[tuple[str, str]] = []
        parser = ActionParser(
            on_text=lambda t: texts.append(t),
            on_file_action=lambda p, c: files.append((p, c)),
        )

        parser.feed("Just some plain text with no XML")
        parser.flush()

        assert len(files) == 0
        assert "plain text" in "".join(texts)


class TestActionParserEdgeCases:
    def test_multiline_file_content(self) -> None:
        files: list[tuple[str, str]] = []
        parser = ActionParser(on_file_action=lambda p, c: files.append((p, c)))

        content = "line 1\nline 2\nline 3\n"
        parser.feed(
            f'<flowArtifact id="test" title="test">'
            f'<flowAction type="file" filePath="multi.ts">'
            f"{content}"
            f"</flowAction>"
            f"</flowArtifact>"
        )
        parser.flush()

        assert len(files) == 1
        assert "line 1" in files[0][1]
        assert "line 3" in files[0][1]

    def test_file_content_with_html_like_content(self) -> None:
        """File content containing < and > should not confuse the parser."""
        files: list[tuple[str, str]] = []
        parser = ActionParser(on_file_action=lambda p, c: files.append((p, c)))

        parser.feed(
            '<flowArtifact id="test" title="test">'
            '<flowAction type="file" filePath="app.tsx">'
            "return <div className='test'>hello</div>"
            "</flowAction>"
            "</flowArtifact>"
        )
        parser.flush()

        assert len(files) == 1
        assert "<div" in files[0][1]

    def test_cdata_stripped(self) -> None:
        """CDATA wrappers should be removed from file content."""
        files: list[tuple[str, str]] = []
        parser = ActionParser(on_file_action=lambda p, c: files.append((p, c)))

        parser.feed(
            '<flowArtifact id="test" title="test">'
            '<flowAction type="file" filePath="app.tsx">'
            "<![CDATA[export default function App() {\n  return <h1>Hello</h1>;\n}]]>"
            "</flowAction>"
            "</flowArtifact>"
        )
        parser.flush()

        assert len(files) == 1
        assert "CDATA" not in files[0][1]
        assert "export default function App()" in files[0][1]
        assert "<h1>Hello</h1>" in files[0][1]

    def test_multiple_cdata_sections(self) -> None:
        """Multiple CDATA sections in one file should all be unwrapped."""
        files: list[tuple[str, str]] = []
        parser = ActionParser(on_file_action=lambda p, c: files.append((p, c)))

        parser.feed(
            '<flowArtifact id="test" title="test">'
            '<flowAction type="file" filePath="app.tsx">'
            "<![CDATA[const a = 1;]]>\n<![CDATA[const b = 2;]]>"
            "</flowAction>"
            "</flowArtifact>"
        )
        parser.flush()

        assert len(files) == 1
        assert "const a = 1;" in files[0][1]
        assert "const b = 2;" in files[0][1]
        assert "CDATA" not in files[0][1]


class TestActionParserEdits:
    def test_edit_pairs_keep_inner_indentation(self) -> None:
        edits: list[tuple[str, list[tuple[str, str]]]] = []
        parser = ActionParser(on_edit_action=lambda p, e: edits.append((p, e)))

        parser.feed(
            '<flowArtifact id="test" title="test">\n'
            '  <flowAction type="edit" filePath="src/App.tsx">\n'
            "<search>\n"
            "    const a = 1;\n"
            "</search>\n"
            "<replace>\n"
            "    const a = 2;\n"
            "</replace>\n"
            "<search>const b = 1;</search><replace>const b = 2;</replace>\n"
            "  </flowAction>\n"
            "</flowArtifact>"
        )
        parser.flush()

        assert edits == [
            ("src/App.tsx", [("    const a = 1;", "    const a = 2;"), ("const b = 1;", "const b = 2;")]),
        ]

    def test_edit_trims_closing_tag_indent(self) -> None:
        edits: list[tuple[str, list[tuple[str, str]]]] = []
        parser = ActionParser(on_edit_action=lambda p, e: edits.append((p, e)))

        parser.feed(
            '<flowArtifact id="t" title="t"><flowAction type="edit" filePath="a.ts">'
            "<search>\n  x\n    </search><replace>\n  y\n    </replace>"
            "</flowAction></flowArtifact>"
        )
        parser.flush()

        assert edits == [("a.ts", [("  x", "  y")])]

    def test_edit_split_across_chunks(self) -> None:
        edits: list[tuple[str, list[tuple[str, str]]]] = []
        parser = ActionParser(on_edit_action=lambda p, e: edits.append((p, e)))

        text = (
            '<flowArtifact id="t" title="t"><flowAction type="edit" filePath="a.ts">'
            "<search>old line</search><replace>new line</replace>"
            "</flowAction></flowArtifact>"
        )
        for ch in text:
            parser.feed(ch)
        parser.flush()

        assert edits == [("a.ts", [("old line", "new line")])]

    def test_file_and_edit_actions_are_routed_separately(self) -> None:
        files: list[tuple[str, str]] = []
        edits: list[tuple[str, list[tuple[str, str]]]] = []
        parser = ActionParser(
            on_file_action=lambda p, c: files.append((p, c)),
            on_edit_action=lambda p, e: edits.append((p, e)),
        )

        parser.feed(
            '<flowArtifact id="t" title="t">'
            '<flowAction type="file" filePath="new.ts">export const x = 1;</flowAction>'
            '<flowAction type="edit" filePath="old.ts"><search>a</search><replace>b</replace></flowAction>'
            "</flowArtifact>"
        )
        parser.flush()

        assert files == [("new.ts", "export const x = 1;")]
        assert edits == [("old.ts", [("a", "b")])]
