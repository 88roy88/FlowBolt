"""A data source exists while its generated module is in the workspace, so versions carry it with its files."""

import asyncio
import logging
import os
from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError

from flow44.ai.codegen.data_source_module import PACKAGE_UPDATED_HEADER
from flow44.db.project_data_source import DataSourceContext, get_project_data_sources
from flow44.logic import data_source as ds_source
from flow44.logic.models import DataSourceParamsInfo
from flow44.sandbox.main import PnpmSandbox

logger = logging.getLogger(__name__)

_DIR = "src/dataSources"


class PackageUpdate(BaseModel):
    data_source_id: str
    updated_date: str


class ParamLabel(BaseModel):
    cube_id: str
    name: str
    label: str


def module_path(ds: DataSourceContext) -> str:
    return f"{_DIR}/{ds.sanitized_name}.ts"


def param_labels(ds: DataSourceContext) -> list[ParamLabel]:
    try:
        params = DataSourceParamsInfo.model_validate(ds.params_info).parameters
    except ValidationError:
        return []
    return [
        ParamLabel(
            cube_id=p.cube_id,
            name=p.name,
            label=(p.quick_info and p.quick_info.display_name) or p.display_name or p.name,
        )
        for p in params
    ]


def _exists(sandbox: PnpmSandbox, path: str) -> bool:
    return os.path.isfile(os.path.join(sandbox.workspace_dir, path))


async def list_active(project_id: str, sandbox: PnpmSandbox) -> list[DataSourceContext]:
    return [ds for ds in await get_project_data_sources(project_id) if _exists(sandbox, module_path(ds))]


async def read_package_updated_date(sandbox: PnpmSandbox, ds: DataSourceContext) -> str:
    try:
        content = await sandbox.read_file(module_path(ds))
    except (OSError, UnicodeDecodeError):
        return ""
    first_line = content.split("\n", 1)[0].strip()
    if not first_line.startswith(PACKAGE_UPDATED_HEADER):
        return ""
    return first_line.removeprefix(PACKAGE_UPDATED_HEADER).strip()


def _parse_date(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def is_newer(latest: str, known: str) -> bool:
    latest_date, known_date = _parse_date(latest), _parse_date(known)
    return latest_date is not None and known_date is not None and latest_date > known_date


async def _find_update(sandbox: PnpmSandbox, ds: DataSourceContext, authorization: str | None) -> PackageUpdate | None:
    known = await read_package_updated_date(sandbox, ds)
    if not known:
        return None
    try:
        latest = await ds_source.get_package_updated_date(ds.data_source_id, authorization=authorization)
    except (ds_source.FlapiUpstreamError, ValidationError, ValueError) as exc:
        logger.warning("Couldn't check data source %s for updates: %s", ds.data_source_id, exc)
        return None
    if not latest or not is_newer(latest, known):
        return None
    return PackageUpdate(data_source_id=ds.data_source_id, updated_date=latest)


async def find_updates(
    sandbox: PnpmSandbox, sources: list[DataSourceContext], authorization: str | None
) -> list[PackageUpdate]:
    found = await asyncio.gather(*[_find_update(sandbox, ds, authorization) for ds in sources])
    return [update for update in found if update]
