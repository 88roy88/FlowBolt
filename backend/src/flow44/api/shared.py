from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from flow44.api.deps import get_optional_user_id
from flow44.config import settings
from flow44.db.page_view import PageViewSource
from flow44.db.project import get_project_by_handle
from flow44.integrations.s3 import S3Object
from flow44.services.page_view_service import is_page_load, record_page_view
from flow44.services.shared_service import AppNotPublishedError, get_published_asset

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


@router.get("/{handle}")
async def redirect_published_app(handle: str) -> RedirectResponse:
    return RedirectResponse(url=f"/shared/{handle}/", status_code=308)


# Published apps need no sign-in; a signed-in viewer is still put on the logs (e.g. page_viewed).
@router.get("/{handle}/{path:path}", response_class=Response, dependencies=[Depends(get_optional_user_id)])
async def proxy_published_asset(request: Request, handle: str, path: str) -> Response:
    asset = await _resolve_asset(handle, path)
    if is_page_load(request) and (project := await get_project_by_handle(handle)):
        await record_page_view(project, PageViewSource.production)
    headers = _cache_headers(asset)
    if asset.etag and request.headers.get("if-none-match") == asset.etag:
        return Response(status_code=304, headers=headers)
    return Response(content=asset.body, media_type=asset.content_type, headers=headers)
