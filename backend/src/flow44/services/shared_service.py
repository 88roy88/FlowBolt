import posixpath

from flow44.db.project import get_project_by_handle
from flow44.integrations.s3 import S3Object, s3_storage


class AppNotPublishedError(Exception):
    pass


async def get_published_asset(handle: str, path: str) -> S3Object | None:
    project = await get_project_by_handle(handle)
    if not project or not project.published_at:
        raise AppNotPublishedError(handle)

    asset = await s3_storage.get_asset(project.id, path)
    if asset is None and not posixpath.splitext(path)[1]:
        asset = await s3_storage.get_asset(project.id, "index.html")
    return asset
