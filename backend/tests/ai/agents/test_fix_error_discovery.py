"""Tests for FixErrorAgent file discovery and filtering of pre-existing build errors."""

from __future__ import annotations

from typing import Any

from flow44.ai.agents.fix_error.agent import FixErrorAgent
from flow44.ai.agents.fix_error.build_errors import drop_baseline_errors
from flow44.ai.agents.fix_error.discovery import find_source_path, local_import_candidates
from flow44.ai.agents.fix_error.fix_error_state import FixErrorState


class _FilesSandbox:
    def __init__(self, files: dict[str, str]) -> None:
        self.files = files

    async def read_file(self, path: str) -> str:
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]


async def _noop_emit(_event: dict[str, Any]) -> None:
    return None


def _make_agent(files: dict[str, str]) -> FixErrorAgent:
    agent = FixErrorAgent.__new__(FixErrorAgent)
    agent.sandbox = _FilesSandbox(files)  # type: ignore[assignment]
    agent.project_id = "851b"
    return agent


def _make_state(**kwargs: Any) -> FixErrorState:
    return FixErrorState(project_id="851b", emit_fn=_noop_emit, **{"error_message": "boom", **kwargs})


def test_find_source_path_skips_node_modules() -> None:
    message = (
        "at /ws/node_modules/react/src/index.js:1:1\n"
        r"[vite] Internal server error: C:\ws\851b\src\components\Coin.tsx: Missing semicolon. (6:4)"
    )
    assert find_source_path(None, message) == r"C:\ws\851b\src\components\Coin.tsx"
    assert find_source_path("Uncaught TypeError: x is undefined", None) is None


def test_local_import_candidates_follows_relative_script_imports_only() -> None:
    content = (
        "import React from 'react'\n"
        "import { Coin } from './Coin'\n"
        "import { format } from '../lib/format.ts'\n"
        "export { Side } from './types'\n"
        "import './Coin.css'\n"
    )
    candidates = local_import_candidates("src/components/Flipper.tsx", content)

    assert [c[0] for c in candidates] == ["src/components/Coin.tsx", "src/lib/format.ts", "src/components/types.tsx"]
    assert "src/components/Coin/index.tsx" in candidates[0]
    assert local_import_candidates("src/index.css", "@import './base.css';") == []


async def test_discover_reads_error_file_from_message_and_its_imports() -> None:
    agent = _make_agent(
        {
            "src/App.tsx": "app",
            "src/components/Coin.tsx": "import { flip } from '../lib/flip'\nimport { Side } from './types'",
            "src/lib/flip.ts": "flip",
            "src/components/types.ts": "types",
        }
    )
    state = _make_state(
        error_message=r"Internal server error: C:\ws\851b\src\components\Coin.tsx: Missing semicolon. (6:4)"
    )

    files = await agent._discover_files(state)

    assert state.error_file == "src/components/Coin.tsx"
    assert list(files) == ["src/components/Coin.tsx", "src/lib/flip.ts", "src/components/types.ts"]


async def test_discover_falls_back_to_app_entry_when_error_file_unknown() -> None:
    agent = _make_agent({"src/App.tsx": "import Coin from './components/Coin'", "src/components/Coin.tsx": "coin"})
    state = _make_state(error_message="Uncaught ReferenceError: x is not defined")

    files = await agent._discover_files(state)

    assert list(files) == ["src/App.tsx", "src/components/Coin.tsx"]


_BASELINE = (
    "src/legacy/Old.tsx(3,1): error TS2304: Cannot find name 'gone'.\n"
    "src/components/Coin.tsx(6,4): error TS1005: ';' expected.\n"
)


def test_drop_baseline_errors_removes_only_untouched_pre_existing_errors() -> None:
    after_fix = (
        "src/legacy/Old.tsx(3,1): error TS2304: Cannot find name 'gone'.\n"
        "src/components/Coin.tsx(6,4): error TS1005: ';' expected.\n"
        "src/components/Flipper.tsx(9,2): error TS2322: Type 'string' is not assignable to type 'number'.\n"
        "  Some continuation line.\n"
        "Found 3 errors.\n"
    )

    result = drop_baseline_errors(after_fix, _BASELINE, keep_files={"src/components/Coin.tsx"})

    assert "Old.tsx" not in result
    assert "Coin.tsx(6,4)" in result
    assert "Flipper.tsx(9,2)" in result
    assert "Some continuation line." in result
    assert "Found 3 errors" not in result


def test_drop_baseline_errors_returns_empty_when_only_pre_existing_errors_remain() -> None:
    after_fix = "src/legacy/Old.tsx(3,1): error TS2304: Cannot find name 'gone'.\nFound 1 error.\n"

    assert drop_baseline_errors(after_fix, _BASELINE, keep_files={"src/components/Coin.tsx"}) == ""


def test_drop_baseline_errors_leaves_non_tsc_output_unchanged() -> None:
    vite_error = "[vite]: Rollup failed to resolve import './missing' from 'src/App.tsx'."

    assert drop_baseline_errors(vite_error, vite_error, keep_files=set()) == vite_error
