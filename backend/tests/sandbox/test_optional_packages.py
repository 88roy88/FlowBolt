"""Tests for optional npm package installation verification."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_enable_optional_packages_installs_all_and_verifies(sandbox, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "package.json").write_text('{"dependencies":{}}', encoding="utf-8")
    commands: list[str] = []

    async def fake_exec(command: str) -> AsyncIterator[str]:
        commands.append(command)
        dependencies = {"react-router-dom": "latest", "regraph": "latest"}
        (tmp_path / "package.json").write_text(json.dumps({"dependencies": dependencies}), encoding="utf-8")
        for package in dependencies:
            (tmp_path / "node_modules" / package).mkdir(parents=True, exist_ok=True)
        yield "installed"

    sandbox.exec = fake_exec

    await sandbox.enable_optional_packages(["react-router-dom", "regraph", "react-router-dom"])

    assert commands == ["pnpm add react-router-dom regraph 2>&1"]


@pytest.mark.asyncio
async def test_enable_optional_packages_fails_when_package_is_unavailable(sandbox, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "package.json").write_text('{"dependencies":{}}', encoding="utf-8")

    async def fake_exec(command: str) -> AsyncIterator[str]:
        del command
        yield "failed"

    sandbox.exec = fake_exec

    with pytest.raises(RuntimeError, match="react-router-dom"):
        await sandbox.enable_optional_packages(["react-router-dom"])
