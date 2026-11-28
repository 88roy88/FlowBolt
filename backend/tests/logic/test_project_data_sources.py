from pathlib import Path

import pytest

from flow44.db.project_data_source import DataSourceContext
from flow44.integrations.flapi.models import PackageMetadata
from flow44.logic import data_source as ds_source
from flow44.logic import project_data_sources as ds_logic
from flow44.sandbox.base import SandboxInfo

from ..api.test_files_api import APITestSandbox

DS = DataSourceContext(data_source_id="12", data_source_name="Sales", sanitized_name="Sales")


def _sandbox(root: Path) -> APITestSandbox:
    return APITestSandbox(SandboxInfo(project_id="p", workspace_dir=str(root), port=0))


def _write(root: Path, path: str, content: str) -> None:
    full = root / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


@pytest.mark.parametrize(
    ("file", "content"),
    [
        ("src/App.tsx", "import { dataSourceSales } from './dataSources/Sales';"),
        ("src/components/deep/Chart.tsx", 'import { dataSourceSales } from "../../dataSources/Sales.ts";'),
        ("src/types.ts", "import type { SalesResults } from './dataSources/Sales';"),
        ("src/dataSources/index.ts", "export * from './Sales';"),
        ("src/lazy.ts", "const load = () => import(`./dataSources/Sales`);"),
        ("src/aliased.ts", "import { dataSourceSales } from '@/dataSources/Sales';"),
        ("src/raw.ts", "fetch(`${API_BASE}/api/data-source/12/run`);"),
        ("src/wrapped.ts", "import {\n  dataSourceSales,\n} from './dataSources/Sales';"),
    ],
)
async def test_find_usages_reports_code_that_reaches_the_source(tmp_path: Path, file: str, content: str) -> None:
    _write(tmp_path, file, content)

    usages = await ds_logic.find_usages(_sandbox(tmp_path), DS)

    assert [u.file for u in usages] == [file]
    assert usages[0].line == (3 if file == "src/wrapped.ts" else 1)


@pytest.mark.parametrize(
    ("file", "content"),
    [
        ("src/App.tsx", "import { Sales } from './components/Sales';"),
        ("src/components/Page.tsx", "import { Sales } from './Sales';"),
        ("src/pages/Page.tsx", "import x from '../components/dataSources/Sales';"),
        ("src/App.tsx", "import { dataSourceSalesByRegion } from './dataSources/SalesByRegion';"),
        ("src/App.tsx", "const title = 'Sales';"),
        ("src/raw.ts", "fetch('/api/data-source/123/run');"),
        ("src/dataSources/Sales.ts", "fetchDataSource('/api/data-source/12/run');"),
        ("src/dataSources/Sales.docs.md", "import { dataSourceSales } from './dataSources/Sales';"),
        ("src/node_modules/pkg/index.js", "require('./dataSources/Sales')"),
    ],
)
async def test_find_usages_ignores_everything_else(tmp_path: Path, file: str, content: str) -> None:
    _write(tmp_path, file, content)

    assert await ds_logic.find_usages(_sandbox(tmp_path), DS) == []


async def test_delete_module_removes_both_files_and_tolerates_missing_docs(tmp_path: Path) -> None:
    _write(tmp_path, "src/dataSources/Sales.ts", "export {}")

    await ds_logic.delete_module(_sandbox(tmp_path), DS)

    assert not (tmp_path / "src/dataSources/Sales.ts").exists()


@pytest.mark.parametrize(
    ("latest", "known", "newer"),
    [
        ("2024-02-12T00:00:00.000", "2024-02-11T00:00:00.000", True),
        ("2024-02-11T00:00:00.001", "2024-02-11T00:00:00.000", True),
        ("2024-02-11T00:00:00.000", "2024-02-11T00:00:00", False),
        ("2024-02-10T00:00:00.000", "2024-02-11T00:00:00.000", False),
        ("2024-02-11T10:00:00.000", "2024-02-11T10:00:00+00:00", False),
        ("2024-02-11T11:00:00+00:00", "2024-02-11T10:00:00.000", True),
        ("yesterday", "2024-02-11T00:00:00.000", False),
        ("2024-02-11T00:00:00.000", "yesterday", False),
    ],
)
def test_is_newer(latest: str, known: str, newer: bool) -> None:
    assert ds_logic.is_newer(latest, known) is newer


async def test_find_updates_skips_unrecorded_and_failing_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    names = {"1": "Outdated", "2": "Current", "3": "Unrecorded", "4": "Failing", "5": "Undated"}
    sources = [DataSourceContext(data_source_id=i, sanitized_name=name) for i, name in names.items()]
    for ds in sources:
        header = "" if ds.sanitized_name == "Unrecorded" else "// Package updated: 2024-02-11T00:00:00.000\n"
        _write(tmp_path, ds_logic.module_path(ds), f"{header}export {{}}\n")
    asked: list[str] = []

    async def latest(data_source_id: str, *, authorization: str | None = None) -> str | None:
        asked.append(data_source_id)
        assert authorization == "token"
        if data_source_id == "4":
            raise ds_source.FlapiUpstreamError("down")
        return {"1": "2024-05-01T00:00:00.000", "2": "2024-02-11T00:00:00.000", "5": None}[data_source_id]

    monkeypatch.setattr(ds_source, "get_package_updated_date", latest)

    updates = await ds_logic.find_updates(_sandbox(tmp_path), sources, "token")

    assert [(u.data_source_id, u.updated_date) for u in updates] == [("1", "2024-05-01T00:00:00.000")]
    assert sorted(asked) == ["1", "2", "4", "5"]


def test_package_metadata_reads_updated_date_and_works_without_it() -> None:
    metadata = {"Id": 1, "Name": "Sales", "Queries": []}

    assert PackageMetadata.model_validate(metadata).updated_date is None
    dated = PackageMetadata.model_validate({**metadata, "UpdatedDate": "2024-02-11T00:00:00.000"})
    assert dated.updated_date == "2024-02-11T00:00:00.000"


@pytest.mark.parametrize(
    ("quick_name", "display_name", "label"),
    [("From quick info", "From param", "From quick info"), (None, "From param", "From param"), ("", "", "raw_name")],
)
def test_param_labels_fall_back_like_the_module_comments(quick_name: str | None, display_name: str, label: str) -> None:
    param = {
        "name": "raw_name",
        "display_name": display_name,
        "quick_info": {"display_name": quick_name},
        "type": "string",
        "is_required": False,
        "is_single_value": True,
        "cube_id": "cube",
    }
    ds = DataSourceContext(params_info={"parameters": [param]})

    assert ds_logic.param_labels(ds) == [ds_logic.ParamLabel(cube_id="cube", name="raw_name", label=label)]


def test_param_labels_are_empty_for_unreadable_params_info() -> None:
    assert ds_logic.param_labels(DataSourceContext(params_info={})) == []
