"""Tests for FileSystemMixin — all real I/O, no mocks."""

import pytest

from .conftest import DummySandbox


@pytest.mark.asyncio
class TestReadWrite:
    async def test_roundtrip(self, sandbox: DummySandbox) -> None:
        await sandbox.write_file("hello.txt", "world")
        assert await sandbox.read_file("hello.txt") == "world"

    async def test_write_creates_parent_dirs(self, sandbox: DummySandbox) -> None:
        await sandbox.write_file("src/a/b.txt", "nested")
        assert await sandbox.read_file("src/a/b.txt") == "nested"

    async def test_read_missing_raises(self, sandbox: DummySandbox) -> None:
        with pytest.raises(FileNotFoundError):
            await sandbox.read_file("does_not_exist.txt")


@pytest.mark.asyncio
class TestEditFile:
    async def test_replaces_content(self, sandbox: DummySandbox) -> None:
        await sandbox.write_file("f.txt", "hello world")
        await sandbox.edit_file("f.txt", "world", "there")
        assert await sandbox.read_file("f.txt") == "hello there"

    async def test_missing_search_raises(self, sandbox: DummySandbox) -> None:
        await sandbox.write_file("f.txt", "hello world")
        with pytest.raises(ValueError, match="Search string not found"):
            await sandbox.edit_file("f.txt", "NOPE", "x")


@pytest.mark.asyncio
class TestDeleteFile:
    async def test_removes_file(self, sandbox: DummySandbox, tmp_path) -> None:  # type: ignore[type-arg]
        await sandbox.write_file("del.txt", "bye")
        await sandbox.delete_file("del.txt")
        assert not (tmp_path / "del.txt").exists()

    async def test_traversal_blocked(self, sandbox: DummySandbox) -> None:
        with pytest.raises(PermissionError):
            await sandbox.delete_file("../../etc/passwd")

    async def test_removes_non_empty_directory_recursively(
        self, sandbox: DummySandbox, tmp_path  # type: ignore[type-arg]
    ) -> None:
        await sandbox.write_file("src/assets/logo.svg", "<svg></svg>")
        await sandbox.delete_file("src")
        assert not (tmp_path / "src").exists()


@pytest.mark.asyncio
class TestCreateRenameAndBinary:
    async def test_create_file_creates_parent_dirs(self, sandbox: DummySandbox) -> None:
        await sandbox.create_file("src/new-file.ts", "export const x = 1;\n")
        assert await sandbox.read_file("src/new-file.ts") == "export const x = 1;\n"

    async def test_create_file_conflict_raises(self, sandbox: DummySandbox) -> None:
        await sandbox.create_file("dup.txt", "a")
        with pytest.raises(FileExistsError):
            await sandbox.create_file("dup.txt", "b")

    async def test_rename_path_for_file(self, sandbox: DummySandbox) -> None:
        await sandbox.write_file("src/old.ts", "content")
        await sandbox.rename_path("src/old.ts", "src/new.ts")
        assert await sandbox.read_file("src/new.ts") == "content"
        with pytest.raises(FileNotFoundError):
            await sandbox.read_file("src/old.ts")

    async def test_rename_path_for_directory_with_children(self, sandbox: DummySandbox) -> None:
        await sandbox.write_file("src/components/Button.tsx", "export const Button = () => null;")
        await sandbox.rename_path("src/components", "src/ui")
        assert await sandbox.read_file("src/ui/Button.tsx") == "export const Button = () => null;"
        with pytest.raises(FileNotFoundError):
            await sandbox.read_file("src/components/Button.tsx")

    async def test_rename_missing_source_raises(self, sandbox: DummySandbox) -> None:
        with pytest.raises(FileNotFoundError):
            await sandbox.rename_path("missing.ts", "new.ts")

    async def test_rename_existing_destination_raises(self, sandbox: DummySandbox) -> None:
        await sandbox.write_file("src/a.ts", "a")
        await sandbox.write_file("src/b.ts", "b")
        with pytest.raises(FileExistsError):
            await sandbox.rename_path("src/a.ts", "src/b.ts")

    async def test_write_binary_file_roundtrip(self, sandbox: DummySandbox, tmp_path) -> None:  # type: ignore[type-arg]
        payload = b"\x89PNG\r\n\x1a\n"
        await sandbox.write_binary_file("src/assets/logo.png", payload)
        assert (tmp_path / "src" / "assets" / "logo.png").read_bytes() == payload

    async def test_write_binary_file_conflict_raises(self, sandbox: DummySandbox) -> None:
        await sandbox.write_file("dup.bin", "text")
        with pytest.raises(FileExistsError):
            await sandbox.write_binary_file("dup.bin", b"binary")

    async def test_write_binary_file_traversal_blocked(self, sandbox: DummySandbox) -> None:
        with pytest.raises(PermissionError, match="Path traversal"):
            await sandbox.write_binary_file("../../tmp/payload.bin", b"x")


@pytest.mark.asyncio
class TestPathTraversal:
    """Verify that all file operations prevent path traversal attacks."""

    async def test_read_file_traversal_blocked(self, sandbox: DummySandbox) -> None:
        with pytest.raises(PermissionError, match="Path traversal"):
            await sandbox.read_file("../../etc/passwd")

    async def test_write_file_traversal_blocked(self, sandbox: DummySandbox) -> None:
        with pytest.raises(PermissionError, match="Path traversal"):
            await sandbox.write_file("../../tmp/malicious", "data")

    async def test_edit_file_traversal_blocked(self, sandbox: DummySandbox) -> None:
        with pytest.raises(PermissionError, match="Path traversal"):
            await sandbox.edit_file("../../etc/passwd", "old", "new")

    async def test_list_files_traversal_blocked(self, sandbox: DummySandbox) -> None:
        with pytest.raises(PermissionError, match="Path traversal"):
            await sandbox.list_files("../../etc")

    async def test_dotdot_in_middle_blocked(self, sandbox: DummySandbox) -> None:
        """Test that ../.. in the middle of a path is also blocked."""
        with pytest.raises(PermissionError, match="Path traversal"):
            await sandbox.read_file("src/../../etc/passwd")

    async def test_symlink_escape_blocked(self, sandbox: DummySandbox, tmp_path) -> None:  # type: ignore[type-arg]
        """Test that symlinks pointing outside workspace are blocked."""
        # Create a symlink pointing outside the workspace
        outside_file = tmp_path.parent / "outside.txt"
        outside_file.write_text("sensitive data")
        symlink_path = tmp_path / "link"
        symlink_path.symlink_to(outside_file)

        # Attempting to read through the symlink should fail
        with pytest.raises(PermissionError, match="Path traversal"):
            await sandbox.read_file("link")


@pytest.mark.asyncio
class TestListFiles:
    async def test_returns_tree(self, sandbox: DummySandbox) -> None:
        await sandbox.write_file("src/App.tsx", "")
        await sandbox.write_file("src/index.ts", "")
        entries = await sandbox.list_files("/")
        names = [e.name for e in entries]
        assert "src" in names
        src = next(e for e in entries if e.name == "src")
        assert src.is_directory
        assert src.children is not None
        child_names = [c.name for c in src.children]
        assert "App.tsx" in child_names
        assert "index.ts" in child_names

    async def test_skips_skip_dirs(self, sandbox: DummySandbox, tmp_path) -> None:  # type: ignore[type-arg]
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg.js").write_text("")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "App.tsx").write_text("")
        entries = await sandbox.list_files("/")
        names = [e.name for e in entries]
        assert "node_modules" not in names
        assert "src" in names

    async def test_not_a_directory_raises(self, sandbox: DummySandbox) -> None:
        await sandbox.write_file("file.txt", "data")
        with pytest.raises(NotADirectoryError):
            await sandbox.list_files("file.txt")
