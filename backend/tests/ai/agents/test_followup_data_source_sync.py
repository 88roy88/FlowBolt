from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from flow44.ai.agents import _chat_agent
from flow44.ai.agents.file_diffs import DiffTracker
from flow44.ai.agents.followup import agent as followup
from flow44.ai.agents.followup.prompts import render_followup
from flow44.db.project_data_source import DataSourceContext
from flow44.sandbox.base import SandboxInfo

from ...api.test_files_api import APITestSandbox


def _context(name: str, sanitized: str, date: str, field: str = "total") -> DataSourceContext:
    return DataSourceContext(
        data_source_id="12",
        data_source_name=name,
        sanitized_name=sanitized,
        package_updated_date=date,
        queries=[
            {
                "name": "rows",
                "display_name": "rows",
                "description": "",
                "fields": [{"name": field, "display_name": field, "type": "int"}],
            }
        ],
        params_info={"parameters": []},
    )


async def _sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fetched: DataSourceContext, stored: DataSourceContext
) -> dict[str, str]:
    """Regenerate over the stored source's module, as a run with the source attached does."""
    agent = object.__new__(followup.FollowUpAgent)
    agent.project_id = "p"
    agent.sandbox = APITestSandbox(SandboxInfo(project_id="p", workspace_dir=str(tmp_path), port=0))
    agent._diffs = DiffTracker()
    agent._data_source_authorization = None
    agent.model = None
    monkeypatch.setattr(_chat_agent, "emit_transient", AsyncMock())
    for path, content in followup.generate_data_source_files(stored).items():
        await agent.sandbox.write_file(path, content)
    monkeypatch.setattr(followup, "fetch_and_analyze_data_source", AsyncMock(return_value=fetched))
    changes: dict[str, str] = {}
    await agent._fetch_analyze_and_write("12", "sync", stored, changes)
    return changes


async def test_a_renamed_package_keeps_its_module_and_reports_what_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stored = _context("Sales", "Sales", "2024-02-11", field="total")
    fetched = _context("Sales Report", "SalesReport", "2024-03-01", field="total_amount")

    changes = await _sync(tmp_path, monkeypatch, fetched, stored)

    assert sorted(p.name for p in (tmp_path / "src/dataSources").iterdir()) == ["Sales.docs.md", "Sales.ts"]
    module = (tmp_path / "src/dataSources/Sales.ts").read_text()
    assert module.startswith("// Package updated: 2024-03-01\n")
    assert "export async function dataSourceSales()" in module
    prompt = render_followup(
        project_summary="", file_tree="", existing_data_source_contexts=[fetched], module_changes=changes
    )
    assert "+  total_amount" in prompt
    assert "-  total" in prompt
    assert "Package updated" not in prompt


async def test_a_new_date_alone_is_reported_as_no_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stored = _context("Sales", "Sales", "2024-02-11")
    fetched = _context("Sales", "Sales", "2024-03-01")

    changes = await _sync(tmp_path, monkeypatch, fetched, stored)

    assert changes == {"12": ""}
    prompt = render_followup(
        project_summary="", file_tree="", existing_data_source_contexts=[fetched], module_changes=changes
    )
    assert "Its code is the same as before" in prompt
