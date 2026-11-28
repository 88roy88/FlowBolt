from pathlib import Path
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

from flow44.api import project_data_sources_api
from flow44.config import settings
from flow44.db.chat import get_messages
from flow44.db.events import get_versions
from flow44.db.heartbeat import try_claim_run
from flow44.services.versioning import service as versioning
from flow44.services.versioning.git import Git

from .conftest import DS_MODULE, requires_git

pytestmark = [pytest.mark.asyncio, requires_git]


async def test_delete_commits_the_removal_as_a_user_version(
    data_sources_client: AsyncClient,
    data_sources_url: str,
    project_id: str,
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log = MagicMock()
    monkeypatch.setattr(project_data_sources_api, "log_bi_event", log)
    listed = (await data_sources_client.get(data_sources_url)).json()

    response = await data_sources_client.delete(f"{data_sources_url}/12")

    assert listed == [
        {"data_source_id": "12", "name": "Sales", "module_path": DS_MODULE, "package_updated_date": None, "params": []}
    ]
    assert response.status_code == 204
    log.assert_called_once_with("data_source_removed", data_source_type="flow_package", data_source_id="12")
    assert (await data_sources_client.get(data_sources_url)).json() == []
    assert not await Git(project_id).is_dirty()
    payload = (await get_versions(project_id))[-1].payload
    assert payload["author"] == "user"
    assert sorted(d["path"] for d in payload["diffs"]) == ["src/dataSources/Sales.docs.md", DS_MODULE]
    assert [m.content for m in await get_messages(project_id)] == [
        '[I removed the data source "Sales". Don\'t use it or recreate its files.]'
    ]


async def test_restoring_the_earlier_version_brings_the_source_back(
    data_sources_client: AsyncClient, data_sources_url: str, project_id: str
) -> None:
    (Path(settings.WORKSPACE_BASE_DIR) / project_id / "a.txt").write_text("built")
    target = await versioning.commit_turn(project_id)
    assert target
    await data_sources_client.delete(f"{data_sources_url}/12")

    await versioning.restore_version(project_id, target)

    assert [ds["data_source_id"] for ds in (await data_sources_client.get(data_sources_url)).json()] == ["12"]


async def test_delete_is_refused_while_the_app_uses_the_source(
    data_sources_client: AsyncClient, data_sources_url: str, project_id: str, workspace: Path
) -> None:
    (workspace / "src/App.tsx").write_text("import './dataSources/Sales';")
    await versioning.commit_turn(project_id)

    usages = (await data_sources_client.get(f"{data_sources_url}/12/usages")).json()
    response = await data_sources_client.delete(f"{data_sources_url}/12")

    assert usages == [{"file": "src/App.tsx", "line": 1}]
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "in_use"
    assert response.json()["detail"]["usages"] == usages
    assert (workspace / DS_MODULE).exists()


async def test_delete_is_refused_with_unsaved_edits(
    data_sources_client: AsyncClient, data_sources_url: str, project_id: str, workspace: Path
) -> None:
    (workspace / "notes.txt").write_text("unsaved")

    response = await data_sources_client.delete(f"{data_sources_url}/12")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "dirty_workspace"
    assert (workspace / DS_MODULE).exists()
    assert await Git(project_id).changed_files() == ["notes.txt"]


async def test_delete_is_refused_during_a_run(
    data_sources_client: AsyncClient, data_sources_url: str, project_id: str, workspace: Path
) -> None:
    await try_claim_run(project_id)

    response = await data_sources_client.delete(f"{data_sources_url}/12")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "run_active"
    assert (workspace / DS_MODULE).exists()


async def test_delete_is_refused_before_the_first_build(data_sources_client: AsyncClient, project_id: str) -> None:
    response = await data_sources_client.delete(f"/api/projects/{project_id}/data-sources/12")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "not_built"


async def test_unknown_source_is_not_found(data_sources_client: AsyncClient, data_sources_url: str) -> None:
    assert (await data_sources_client.delete(f"{data_sources_url}/999")).status_code == 404
