"""Tests for optional react-router scaffolding in PnpmMixin."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import AsyncIterator

import pytest

from flow44.config import settings
from flow44.sandbox.base import SandboxInfo
from flow44.sandbox.pnpm_mixin import PnpmMixin


class RoutingTestSandbox(PnpmMixin):
    def __init__(self, workspace_dir: str, template_dir: str) -> None:
        info = SandboxInfo(project_id="routing-test", workspace_dir=workspace_dir, port=9100)
        super().__init__(info)
        self.template_dir = template_dir
        self.exec_commands: list[str] = []

    async def exec(self, command: str) -> AsyncIterator[str]:  # type: ignore[override]
        self.exec_commands.append(command)
        if "pnpm add react-router-dom" in command:
            pkg_path = os.path.join(self.workspace_dir, "package.json")
            with open(pkg_path, encoding="utf-8") as handle:
                pkg = json.load(handle)
            pkg.setdefault("dependencies", {})["react-router-dom"] = "^6.28.0"
            with open(pkg_path, "w", encoding="utf-8") as handle:
                json.dump(pkg, handle, indent=2)
            yield "react-router-dom added"
        elif "pnpm install" in command:
            yield "install ok"
        else:
            yield ""

    async def _spawn_background(self, name: str, command: str, env: dict[str, str]) -> None:
        raise NotImplementedError

    def create_pty(self):  # type: ignore[override]
        raise NotImplementedError

    @classmethod
    def find_pids_in_port_range(cls, port_start: int, port_end: int) -> list[tuple[int, int]]:
        raise NotImplementedError

    @classmethod
    def kill_pid(cls, pid: int) -> None:
        raise NotImplementedError


@pytest.fixture
def template_workspace(tmp_path):  # type: ignore[type-arg]
    template_dir = tmp_path / "template"
    workspace_dir = tmp_path / "workspace"
    shutil.copytree(settings.TEMPLATE_DIR, template_dir)
    return str(template_dir), str(workspace_dir)


class TestPnpmRouting:
    @pytest.mark.asyncio
    async def test_scaffold_removes_routing_stub(self, template_workspace) -> None:
        template_dir, workspace_dir = template_workspace
        sandbox = RoutingTestSandbox(workspace_dir, template_dir)
        await sandbox.scaffold(template_dir)

        assert not os.path.isdir(os.path.join(workspace_dir, "routing-stub"))
        assert os.path.isfile(os.path.join(workspace_dir, "src", "utils", "routerBasename.ts"))
        assert not os.path.isfile(os.path.join(workspace_dir, "src", "router", "AppRouter.tsx"))

    @pytest.mark.asyncio
    async def test_enable_client_routing_installs_and_copies(self, template_workspace) -> None:
        template_dir, workspace_dir = template_workspace
        sandbox = RoutingTestSandbox(workspace_dir, template_dir)
        shutil.copytree(template_dir, workspace_dir, dirs_exist_ok=True)
        sandbox._remove_routing_stub_from_workspace()

        await sandbox.enable_client_routing(template_dir)

        assert any("pnpm add react-router-dom" in cmd for cmd in sandbox.exec_commands)
        router_file = os.path.join(workspace_dir, "src", "router", "AppRouter.tsx")
        assert os.path.isfile(router_file)
        with open(router_file, encoding="utf-8") as handle:
            content = handle.read()
        assert "BrowserRouter" in content
        assert "getRouterBasename" in content

        with open(os.path.join(workspace_dir, "package.json"), encoding="utf-8") as handle:
            pkg = json.load(handle)
        assert "react-router-dom" in pkg.get("dependencies", {})

    @pytest.mark.asyncio
    async def test_enable_client_routing_is_idempotent(self, template_workspace) -> None:
        template_dir, workspace_dir = template_workspace
        sandbox = RoutingTestSandbox(workspace_dir, template_dir)
        shutil.copytree(template_dir, workspace_dir, dirs_exist_ok=True)
        sandbox._remove_routing_stub_from_workspace()

        await sandbox.enable_client_routing(template_dir)
        await sandbox.enable_client_routing(template_dir)

        add_commands = [cmd for cmd in sandbox.exec_commands if "pnpm add react-router-dom" in cmd]
        assert len(add_commands) == 1
