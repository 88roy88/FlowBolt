"""Tests for UnixSandbox.exec() — real subprocess in tmp workspace."""

import os

import pytest

from flow44.sandbox.base import SandboxInfo
from flow44.sandbox.unix_local import UnixSandbox


@pytest.fixture
def sandbox(tmp_path):  # type: ignore[type-arg]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    info = SandboxInfo(project_id="test", workspace_dir=str(workspace), port=0)
    return UnixSandbox(info)


async def _collect(gen) -> list[str]:  # type: ignore[type-arg]
    return [line async for line in gen]


@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="UnixSandbox.exec tests require /bin/bash")
class TestUnixSandboxExec:
    async def test_echo(self, sandbox: UnixSandbox) -> None:
        lines = await _collect(sandbox.exec("echo hello"))
        assert "".join(lines).strip() == "hello"

    async def test_multiline_output(self, sandbox: UnixSandbox) -> None:
        lines = await _collect(sandbox.exec("printf 'a\\nb\\nc\\n'"))
        joined = "".join(lines)
        assert joined.count("\n") >= 3

    async def test_stderr_captured(self, sandbox: UnixSandbox) -> None:
        # UnixSandbox merges stderr into stdout
        lines = await _collect(sandbox.exec("echo err >&2"))
        assert any("err" in line for line in lines)

    async def test_failed_command_does_not_raise(self, sandbox: UnixSandbox) -> None:
        # exec should complete without exception even when exit code is non-zero
        lines = await _collect(sandbox.exec("exit 1"))
        assert isinstance(lines, list)

    async def test_pwd_is_workspace(self, sandbox: UnixSandbox) -> None:
        lines = await _collect(sandbox.exec("pwd"))
        output = "".join(lines).strip()
        assert os.path.realpath(output) == os.path.realpath(sandbox.workspace_dir)

    async def test_creates_file_in_workspace(self, sandbox: UnixSandbox, tmp_path) -> None:  # type: ignore[type-arg]
        await _collect(sandbox.exec("echo content > test.txt"))
        file_path = tmp_path / "workspace" / "test.txt"
        assert file_path.exists()
        assert file_path.read_text().strip() == "content"

    async def test_reads_file_from_workspace(self, sandbox: UnixSandbox, tmp_path) -> None:  # type: ignore[type-arg]
        (tmp_path / "workspace" / "data.txt").write_text("hello from file")
        lines = await _collect(sandbox.exec("cat data.txt"))
        assert "hello from file" in "".join(lines)
