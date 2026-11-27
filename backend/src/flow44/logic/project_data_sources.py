"""The data sources a project's code can use, and removing them.

A data source exists while its generated module is in the workspace. The DB rows are kept after a removal,
so restoring or rolling back a version brings the data source back along with its files.
"""

import asyncio
import logging
import os
import posixpath
import re
from collections.abc import Iterator
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ValidationError

from flow44.ai.codegen.data_source_module import PACKAGE_UPDATED_HEADER
from flow44.db.project_data_source import DataSourceContext, get_project_data_sources
from flow44.logic import data_source as ds_source
from flow44.sandbox.constants import SKIP_DIRS
from flow44.sandbox.main import PnpmSandbox

logger = logging.getLogger(__name__)

_DIR = "src/dataSources"
_SOURCE_SUFFIXES = (".ts", ".tsx", ".js", ".jsx")


class Usage(BaseModel):
    file: str  # workspace-relative path
    line: int


class PackageUpdate(BaseModel):
    data_source_id: str
    updated_date: str  # the package's current one, newer than the module's


class DataSourceInUse(RuntimeError):
    def __init__(self, usages: list[Usage]) -> None:
        super().__init__(f"Data source is used in {len(usages)} place(s)")
        self.usages = usages


def module_path(ds: DataSourceContext) -> str:
    return f"{_DIR}/{ds.sanitized_name}.ts"


def _exists(sandbox: PnpmSandbox, path: str) -> bool:
    return os.path.isfile(os.path.join(sandbox.workspace_dir, path))


async def list_active(project_id: str, sandbox: PnpmSandbox) -> list[DataSourceContext]:
    return [ds for ds in await get_project_data_sources(project_id) if _exists(sandbox, module_path(ds))]


def _source_files(workspace: Path) -> Iterator[tuple[str, str]]:
    for root, dirs, names in os.walk(workspace / "src"):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            path = Path(root, name)
            if name.endswith(_SOURCE_SUFFIXES) and not path.is_symlink():
                yield path.relative_to(workspace).as_posix(), path.read_text(encoding="utf-8", errors="replace")


def _points_to_module(specifier: str, importer: str, name: str) -> bool:
    target = re.sub(r"\.[jt]sx?$", "", specifier)
    module = f"{_DIR}/{name}"
    if target.startswith("."):
        return posixpath.normpath(posixpath.join(posixpath.dirname(importer), target)) == module
    target = target.lstrip("/")
    # The template has no import aliases; this covers a project that added one.
    return target in (module, f"dataSources/{name}") or target.endswith(f"/dataSources/{name}")


def _scan(workspace: Path, ds: DataSourceContext) -> list[Usage]:
    name = ds.sanitized_name
    quoted_path = re.compile(rf"""["'`]([^"'`\n]*/{re.escape(name)}(?:\.[jt]sx?)?)["'`]""")
    run_url = f"data-source/{ds.data_source_id}/"
    usages: list[Usage] = []
    for file, content in _source_files(workspace):
        if file == module_path(ds):
            continue
        for number, line in enumerate(content.split("\n"), start=1):
            if run_url in line or any(_points_to_module(m[1], file, name) for m in quoted_path.finditer(line)):
                usages.append(Usage(file=file, line=number))
    return sorted(usages, key=lambda u: (u.file, u.line))


async def find_usages(sandbox: PnpmSandbox, ds: DataSourceContext) -> list[Usage]:
    """Where the app's code imports the data source's module or calls its run URL directly.

    Reads the files itself rather than using `sandbox.grep`: a failed search command returns no output there,
    which would look like "unused" and let the removal through.
    """
    return await asyncio.to_thread(_scan, Path(sandbox.workspace_dir), ds)


async def delete_module(sandbox: PnpmSandbox, ds: DataSourceContext) -> None:
    """Delete the generated files, refusing while the app still uses them."""
    if usages := await find_usages(sandbox, ds):
        raise DataSourceInUse(usages)
    for path in (module_path(ds), f"{_DIR}/{ds.sanitized_name}.docs.md"):
        with suppress(FileNotFoundError):
            await sandbox.delete_file(path)


async def read_package_updated_date(sandbox: PnpmSandbox, ds: DataSourceContext) -> str:
    """The package date the module was generated from, or "" if it doesn't record one."""
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
    """Whether `latest` is a later date than `known`. False if either can't be read."""
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
    """The data sources whose package is newer than their module. One that can't be checked is left out."""
    found = await asyncio.gather(*[_find_update(sandbox, ds, authorization) for ds in sources])
    return [update for update in found if update]
