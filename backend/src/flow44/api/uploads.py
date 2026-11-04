import mimetypes
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel

from flow44.ai.attachments import attachment_kind
from flow44.api.deps import Permission, ProjectDep, UserDep, require_permission
from flow44.config import settings
from flow44.db.uploads import Upload, UploadKind, get_upload, save_upload, upload_key
from flow44.integrations.s3 import s3_storage
from flow44.services.logging import log_bi_event

router = APIRouter(prefix="/api/uploads/{project_id}", tags=["uploads"])


class UploadResponse(BaseModel):
    id: str
    name: str
    content_type: str
    size_bytes: int
    width: int | None
    height: int | None


class _TooLarge(Exception):
    pass


def _resolve_content_type(header: str | None, name: str) -> str:
    content_type = (header or "").split(";")[0].strip().lower()
    if not content_type or content_type == "application/octet-stream":
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return content_type


def _too_large() -> HTTPException:
    limit_mb = settings.UPLOAD_MAX_ATTACHMENT_BYTES // (1024 * 1024)
    return HTTPException(status_code=413, detail=f"Attachments are limited to {limit_mb} MB.")


async def _capped(chunks: AsyncIterator[bytes], limit: int) -> AsyncIterator[bytes]:
    received = 0
    async for chunk in chunks:
        received += len(chunk)
        if received > limit:
            raise _TooLarge
        yield chunk


@router.post("/attachments")
async def post_attachment(
    project: ProjectDep,
    user_id: UserDep,
    request: Request,
    name: str = Query(min_length=1, max_length=255),
    width: int | None = Query(default=None, ge=1),
    height: int | None = Query(default=None, ge=1),
    _perms: set[Permission] = require_permission(Permission.write),
) -> UploadResponse:
    name = name.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    content_type = _resolve_content_type(request.headers.get("content-type"), name)
    if attachment_kind(content_type) is None:
        raise HTTPException(status_code=415, detail=f"Can't attach files of type {content_type}.")
    limit = settings.UPLOAD_MAX_ATTACHMENT_BYTES
    if int(request.headers.get("content-length") or 0) > limit:
        raise _too_large()

    upload = Upload(
        project_id=project.id,
        kind=UploadKind.attachment,
        name=name,
        s3_key="",
        content_type=content_type,
        size_bytes=0,
        width=width,
        height=height,
        created_by=user_id,
    )
    upload.s3_key = upload_key(project.id, upload.id)
    try:
        upload.size_bytes = await s3_storage.upload_stream(
            upload.s3_key, _capped(request.stream(), limit), content_type
        )
    except _TooLarge:
        raise _too_large() from None
    upload = await save_upload(upload)

    log_bi_event("attachment_uploaded", content_type=content_type, size_bytes=upload.size_bytes)
    return UploadResponse.model_validate(upload, from_attributes=True)


@router.get("/{upload_id}/content")
async def get_upload_content(
    project: ProjectDep,
    upload_id: str,
    _perms: set[Permission] = require_permission(Permission.read),
) -> Response:
    upload = await get_upload(project.id, upload_id)
    body = await s3_storage.read_upload(upload.s3_key) if upload else None
    if upload is None or body is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return Response(
        content=body,
        media_type=upload.content_type,
        headers={
            # An upload's bytes never change: replacing one creates a new id.
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )
