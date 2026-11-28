from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from flow44.api import project_data_sources_api
from flow44.api.deps import get_project, get_sandbox
from flow44.config import settings
from flow44.db.chat import get_messages
from flow44.db.events import emit_event, get_versions
from flow44.db.heartbeat import try_claim_run
from flow44.db.project_data_source import DataSourceContext, update_project_data_sources
from flow44.logic import data_source as ds_source
from flow44.main import app
from flow44.sandbox.base import SandboxInfo
from flow44.services.versioning import service as versioning
from flow44.services.versioning.git import Git

from ..api.test_files_api import APITestSandbox
from .conftest import requires_git

pytestmark = [pytest.mark.asyncio, requires_git]

MODULE = "src/dataSources/Sales.ts"


@pytest.fixture
def overrides(project_id: str, workspace: Path) -> Iterator[None]:
    project = MagicMock()
    project.id = project_id
    sandbox = APITestSandbox(SandboxInfo(project_id=project_id, workspace_dir=str(workspace), port=0))
    app.dependency_overrides[get_project] = lambda: project
    app.dependency_overrides[get_sandbox] = lambda: sandbox
    yield
    app.dependency_overrides.pop(get_project, None)
    app.dependency_overrides.pop(get_sandbox, None)


@pytest.fixture
async def client(overrides: None) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        yield http


@pytest.fixture
async def url(project_id: str, workspace: Path) -> str:
    (workspace / "src/dataSources").mkdir(parents=True)
    (workspace / MODULE).write_text("export {}")
    (workspace / "src/dataSources/Sales.docs.md").write_text("docs")
    await versioning.ensure_repo(project_id)
    await update_project_data_sources(
        project_id, [DataSourceContext(data_source_id="12", data_source_name="Sales", sanitized_name="Sales")]
    )
    await emit_event(project_id, {"type": "action_complete"})
    return f"/api/projects/{project_id}/data-sources"


async def test_delete_commits_the_removal_as_a_user_version(
    client: AsyncClient, url: str, project_id: str, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = MagicMock()
    monkeypatch.setattr(project_data_sources_api, "log_bi_event", log)
    listed = (await client.get(url)).json()

    response = await client.delete(f"{url}/12")

    assert listed == [
        {"data_source_id": "12", "name": "Sales", "module_path": MODULE, "package_updated_date": None, "params": []}
    ]
    assert response.status_code == 204
    log.assert_called_once_with("data_source_removed", data_source_type="flow_package", data_source_id="12")
    assert (await client.get(url)).json() == []
    assert not await Git(project_id).is_dirty()
    payload = (await get_versions(project_id))[-1].payload
    assert payload["author"] == "user"
    assert sorted(d["path"] for d in payload["diffs"]) == ["src/dataSources/Sales.docs.md", MODULE]
    assert [m.content for m in await get_messages(project_id)] == [
        '[I removed the data source "Sales". Don\'t use it or recreate its files.]'
    ]


async def test_restoring_the_earlier_version_brings_the_source_back(
    client: AsyncClient, url: str, project_id: str
) -> None:
    (Path(settings.WORKSPACE_BASE_DIR) / project_id / "a.txt").write_text("built")
    target = await versioning.commit_turn(project_id)
    assert target
    await client.delete(f"{url}/12")

    await versioning.restore_version(project_id, target)

    assert [ds["data_source_id"] for ds in (await client.get(url)).json()] == ["12"]


async def test_delete_is_refused_while_the_app_uses_the_source(
    client: AsyncClient, url: str, project_id: str, workspace: Path
) -> None:
    (workspace / "src/App.tsx").write_text("import './dataSources/Sales';")
    await versioning.commit_turn(project_id)

    usages = (await client.get(f"{url}/12/usages")).json()
    response = await client.delete(f"{url}/12")

    assert usages == [{"file": "src/App.tsx", "line": 1}]
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "in_use"
    assert response.json()["detail"]["usages"] == usages
    assert (workspace / MODULE).exists()


async def test_delete_is_refused_with_unsaved_edits(
    client: AsyncClient, url: str, project_id: str, workspace: Path
) -> None:
    (workspace / "notes.txt").write_text("unsaved")

    response = await client.delete(f"{url}/12")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "dirty_workspace"
    assert (workspace / MODULE).exists()
    assert await Git(project_id).changed_files() == ["notes.txt"]


async def test_delete_is_refused_during_a_run(client: AsyncClient, url: str, project_id: str, workspace: Path) -> None:
    await try_claim_run(project_id)

    response = await client.delete(f"{url}/12")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "run_active"
    assert (workspace / MODULE).exists()


async def test_delete_is_refused_before_the_first_build(client: AsyncClient, project_id: str) -> None:
    response = await client.delete(f"/api/projects/{project_id}/data-sources/12")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "not_built"


async def test_unknown_source_is_not_found(client: AsyncClient, url: str) -> None:
    assert (await client.delete(f"{url}/999")).status_code == 404


async def test_restoring_a_version_restores_the_package_date_and_so_the_update(
    client: AsyncClient, url: str, project_id: str, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ds_source, "get_package_updated_date", AsyncMock(return_value="2024-03-01T00:00:00.000"))
    (workspace / MODULE).write_text("// Package updated: 2024-02-11T00:00:00.000\nexport {}\n")
    before_sync = await versioning.commit_turn(project_id)
    assert before_sync
    outdated = (await client.get(f"{url}/updates")).json()

    (workspace / MODULE).write_text("// Package updated: 2024-03-01T00:00:00.000\nexport {}\n")
    await versioning.commit_turn(project_id)
    synced = (await client.get(f"{url}/updates")).json()
    await versioning.restore_version(project_id, before_sync)

    assert outdated == [{"data_source_id": "12", "updated_date": "2024-03-01T00:00:00.000"}]
    assert synced == []
    assert (await client.get(f"{url}/updates")).json() == outdated
    assert (await client.get(url)).json()[0]["package_updated_date"] == "2024-02-11T00:00:00.000"
