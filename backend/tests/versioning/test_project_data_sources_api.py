from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from flow44.logic import data_source as ds_source
from flow44.services.versioning import service as versioning

from .conftest import DS_MODULE, requires_git

pytestmark = [pytest.mark.asyncio, requires_git]


async def test_lists_a_source_only_while_its_module_exists(
    data_sources_client: AsyncClient, data_sources_url: str, workspace: Path
) -> None:
    listed = (await data_sources_client.get(data_sources_url)).json()
    (workspace / DS_MODULE).unlink()

    assert listed == [
        {"data_source_id": "12", "name": "Sales", "module_path": DS_MODULE, "package_updated_date": None, "params": []}
    ]
    assert (await data_sources_client.get(data_sources_url)).json() == []


async def test_restoring_a_version_restores_the_package_date_and_so_the_update(
    data_sources_client: AsyncClient,
    data_sources_url: str,
    project_id: str,
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ds_source, "get_package_updated_date", AsyncMock(return_value="2024-03-01T00:00:00.000"))
    (workspace / DS_MODULE).write_text("// Package updated: 2024-02-11T00:00:00.000\nexport {}\n")
    before_sync = await versioning.commit_turn(project_id)
    assert before_sync
    outdated = (await data_sources_client.get(f"{data_sources_url}/updates")).json()

    (workspace / DS_MODULE).write_text("// Package updated: 2024-03-01T00:00:00.000\nexport {}\n")
    await versioning.commit_turn(project_id)
    synced = (await data_sources_client.get(f"{data_sources_url}/updates")).json()
    await versioning.restore_version(project_id, before_sync)

    assert outdated == [{"data_source_id": "12", "updated_date": "2024-03-01T00:00:00.000"}]
    assert synced == []
    assert (await data_sources_client.get(f"{data_sources_url}/updates")).json() == outdated
    assert (await data_sources_client.get(data_sources_url)).json()[0][
        "package_updated_date"
    ] == "2024-02-11T00:00:00.000"
