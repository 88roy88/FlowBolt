"""Static assets the backend serves, such as scripts injected into previews.

Kept out of /api/preview/{x}, which nginx pins to one pod per project (docs/multi-pod.md).
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/static", tags=["static"])

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

PREVIEW_TOOLBAR_URL = "/api/static/preview_toolbar.js"


@router.get("/preview_toolbar.js")
async def preview_toolbar() -> FileResponse:
    return FileResponse(
        _STATIC_DIR / "preview_toolbar.js",
        media_type="application/javascript; charset=utf-8",
        headers={"Cache-Control": "no-cache"},
    )
