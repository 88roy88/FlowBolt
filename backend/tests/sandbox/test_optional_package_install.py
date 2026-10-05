from __future__ import annotations

from collections.abc import AsyncIterator

from flow44.sandbox.pnpm_mixin import PnpmMixin


class _Stub:
    project_id = "proj"

    def __init__(self) -> None:
        self.commands: list[str] = []

    def exec(self, command: str) -> AsyncIterator[str]:
        self.commands.append(command)
        return self._empty()

    @staticmethod
    async def _empty() -> AsyncIterator[str]:
        for _ in ():
            yield _


async def test_empty_list_is_noop() -> None:
    stub = _Stub()
    await PnpmMixin.install_optional_packages(stub, [])  # type: ignore[arg-type]
    assert stub.commands == []


async def test_builds_pnpm_add_command() -> None:
    stub = _Stub()
    await PnpmMixin.install_optional_packages(stub, ["date-fns", "react-hook-form"])  # type: ignore[arg-type]
    assert len(stub.commands) == 1
    command = stub.commands[0]
    assert command.startswith("pnpm add ")
    assert "date-fns" in command and "react-hook-form" in command
    assert command.endswith(" 2>&1")
