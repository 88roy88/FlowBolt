"""configure_npmrc is idempotent and re-applied when an existing workspace is woken."""

from pathlib import Path
from unittest.mock import patch

import pytest

from flow44.sandbox.manager import SandboxManager

from .conftest import DummySandbox


def test_rewrites_stale_store_dir_and_reports_change(sandbox, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / ".npmrc").write_text("store-dir=/old/store\n")
    with patch("flow44.sandbox.pnpm_mixin.settings") as s:
        s.SANDBOX_MODE = "local"
        s.PNPM_STORE_DIR = "/mnt/nfs/.pnpm-store"
        s.NPM_REGISTRY = "https://registry.npmjs.org/"
        s.NPM_STRICT_SSL = True
        s.NPM_AUDIT = True
        assert sandbox.configure_npmrc() is True
        assert "store-dir=/mnt/nfs/.pnpm-store" in (tmp_path / ".npmrc").read_text()
        assert sandbox.configure_npmrc() is False  # second call: nothing to change


@pytest.mark.asyncio
async def test_get_sandbox_refreshes_npmrc_for_scaffolded_workspace(tmp_path: Path) -> None:
    ws = tmp_path / "ws" / "proj1"
    ws.mkdir(parents=True)
    (ws / "package.json").write_text("{}")
    (ws / ".npmrc").write_text("store-dir=/old/store\n")
    with (
        patch("flow44.sandbox.manager.settings") as ms,
        patch("flow44.sandbox.base.settings", ms),
        patch("flow44.sandbox.pnpm_mixin.settings", ms),
        patch("flow44.sandbox.manager.workspace_path", return_value=str(ws)),
    ):
        ms.SANDBOX_MODE = "local"
        ms.SANDBOX_PORT_RANGE_START = 19200
        ms.SANDBOX_PORT_RANGE_END = 19210
        ms.PNPM_STORE_DIR = "/mnt/nfs/.pnpm-store"
        ms.NPM_REGISTRY = "https://registry.npmjs.org/"
        ms.NPM_STRICT_SSL = True
        ms.NPM_AUDIT = True
        mgr = SandboxManager()
        with patch.object(SandboxManager, "_get_sandbox_class", return_value=DummySandbox):
            await mgr.get_sandbox("proj1")
    assert "store-dir=/mnt/nfs/.pnpm-store" in (ws / ".npmrc").read_text()
