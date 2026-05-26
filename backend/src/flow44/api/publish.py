import asyncio
import logging
import mimetypes
import os

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from flow44.config import settings
from flow44.db.project import get_project, update_project_published_url
from flow44.integrations.s3 import deploy_published_dist, published_object_url
from flow44.paths import (
    EXPORT_API_PREFIX,
    EXPORT_PUBLISHED_PATH_ROUTE,
    EXPORT_PUBLISHED_ROUTE,
    export_published_base_path,
)
from flow44.sandbox.operations import BuildError, build_dist

logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"{EXPORT_API_PREFIX}/{{project_id}}", tags=["publish"])

_STATIC_EXTENSIONS = frozenset({".css", ".ico", ".jpeg", ".jpg", ".js", ".json", ".map", ".png", ".svg", ".webp", ".woff", ".woff2"})


def _is_static_asset(path: str) -> bool:
    _, ext = os.path.splitext(path.lstrip("/"))
    return ext.lower() in _STATIC_EXTENSIONS


def _s3_urls(project_id: str, published_url: str, path: str) -> list[str]:
    if path.lstrip("/") in ("", "index.html"):
        return [published_object_url(project_id, "index.html"), published_url]
    return [published_object_url(project_id, path)]


def _cache_headers(resp: httpx.Response) -> dict[str, str]:
    headers = {"Cache-Control": f"public, max-age={settings.S3_CACHE_TTL}, must-revalidate"}
    if "etag" in resp.headers:
        headers["ETag"] = resp.headers["etag"]
    if "last-modified" in resp.headers:
        headers["Last-Modified"] = resp.headers["last-modified"]
    return headers


async def _fetch_published_object(project_id: str, path: str, *, spa_fallback: bool = True) -> Response:
    project = await get_project(project_id)
    if not project or not project.published_url:
        raise HTTPException(status_code=404, detail="Published app not found or not published yet.")

    async with httpx.AsyncClient() as client:
        last_error: Exception | None = None
        for url in _s3_urls(project_id, project.published_url, path):
            try:
                resp = await client.get(url, timeout=15.0)
                resp.raise_for_status()
            except Exception as exc:
                last_error = exc
                continue

            if path in ("", "index.html") or url.endswith(".html"):
                return HTMLResponse(content=resp.text, headers=_cache_headers(resp))

            media_type = resp.headers.get("content-type") or mimetypes.guess_type(path)[0]
            return Response(content=resp.content, headers=_cache_headers(resp), media_type=media_type)

        if spa_fallback and path not in ("", "index.html") and not _is_static_asset(path):
            return await _fetch_published_object(project_id, "index.html", spa_fallback=False)

        logger.exception("Failed to fetch published object for project %s path %s", project_id, path or "index.html")
        raise HTTPException(status_code=502, detail="Error fetching published app from S3.") from last_error


@router.post("/publish")
async def publish_to_s3(project_id: str) -> dict[str, str]:
    if settings.S3_BUCKET_NAME is None:
        raise HTTPException(status_code=500, detail="S3_BUCKET_NAME is not set")

    try:
        dist_dir = await build_dist(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BuildError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        loop = asyncio.get_running_loop()
        s3_url = await loop.run_in_executor(None, deploy_published_dist, dist_dir, project_id)
    except Exception as exc:
        logger.exception("S3 deployment failed for project %s", project_id)
        raise HTTPException(status_code=502, detail=f"S3 deployment failed: {exc}") from exc

    await update_project_published_url(project_id, s3_url)
    proxy_path = export_published_base_path(project_id)
    logger.info("Published project %s to %s (proxy: %s)", project_id, s3_url, proxy_path)
    return {"url": proxy_path}


@router.get(EXPORT_PUBLISHED_ROUTE, response_class=HTMLResponse)
async def proxy_published_app(project_id: str) -> HTMLResponse:
    response = await _fetch_published_object(project_id, "index.html")
    if not isinstance(response, HTMLResponse):
        raise HTTPException(status_code=502, detail="Published index is not HTML.")
    return response


@router.get(EXPORT_PUBLISHED_PATH_ROUTE)
async def proxy_published_asset(project_id: str, path: str) -> Response:
    return await _fetch_published_object(project_id, path)
