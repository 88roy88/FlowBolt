import re
from enum import StrEnum

from flow44.db.project import is_handle_taken, update_project_published_url
from flow44.integrations.s3 import s3_storage
from flow44.sandbox.operations import build_dist

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")


class SlugStatus(StrEnum):
    available = "available"
    invalid = "invalid"
    taken = "taken"


async def resolve_slug_status(slug: str, project_id: str) -> SlugStatus:
    if not SLUG_RE.match(slug):
        return SlugStatus.invalid
    if await is_handle_taken(slug, exclude_project_id=project_id):
        return SlugStatus.taken
    return SlugStatus.available


async def publish_project(project_id: str, slug: str | None) -> str:
    files = await build_dist(project_id)
    await s3_storage.deploy_dist(project_id, files)
    handle = slug or project_id
    await update_project_published_url(project_id, handle)
    return handle
