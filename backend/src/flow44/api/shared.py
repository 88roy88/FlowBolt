import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from flow44.api.deps import OptionalUserDep, resolve_project_permissions
from flow44.auth.permissions import Permission, has_permission
from flow44.config import settings
from flow44.db.page_view import PageViewSource
from flow44.db.project import Project, get_project_by_handle
from flow44.integrations.s3 import S3Object
from flow44.services.page_view_service import is_page_load, record_page_view
from flow44.services.shared_service import AppNotPublishedError, get_published_asset

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shared", tags=["shared"])


def _cache_control(path: str) -> str:
    if path.startswith("assets/"):
        return "public, max-age=31536000, immutable"
    if path.endswith(".html"):
        return "no-cache"
    return f"public, max-age={settings.S3_CACHE_TTL}, must-revalidate"


def _cache_headers(asset: S3Object) -> dict[str, str]:
    headers = {"Cache-Control": _cache_control(asset.path)}
    if asset.etag:
        headers["ETag"] = asset.etag
    return headers


async def _resolve_asset(handle: str, path: str) -> S3Object:
    path = path.lstrip("/")
    if ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="Invalid asset path.")
    try:
        asset = await get_published_asset(handle, path or "index.html")
    except AppNotPublishedError as exc:
        raise HTTPException(status_code=404, detail=f"No published app found for handle '{handle}'.") from exc
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset '{path}' not found.")
    return asset


async def _viewer_can_write(project: Project, user_id: str | None) -> bool:
    """Never raises: a failed permission lookup must not affect serving the app."""
    if user_id is None:
        return False
    try:
        return has_permission(await resolve_project_permissions(project, user_id), Permission.write)
    except Exception:
        logger.exception("Failed to resolve page viewer permissions for project %s", project.id)
        return False


@router.get("/{handle}")
async def redirect_published_app(handle: str) -> RedirectResponse:
    return RedirectResponse(url=f"/shared/{handle}/", status_code=308)


@router.get("/{handle}/{path:path}", response_class=Response)
async def proxy_published_asset(request: Request, handle: str, path: str, user_id: OptionalUserDep) -> Response:
    asset = await _resolve_asset(handle, path)
    # Published apps count in iframes too: there an iframe is someone embedding the app, not the builder.
    if is_page_load(request, asset.content_type) and (project := await get_project_by_handle(handle)):
        await record_page_view(project, PageViewSource.production, can_write=await _viewer_can_write(project, user_id))
    headers = _cache_headers(asset)
    if asset.etag and request.headers.get("if-none-match") == asset.etag:
        return Response(status_code=304, headers=headers)
    return Response(content=asset.body, media_type=asset.content_type, headers=headers)
