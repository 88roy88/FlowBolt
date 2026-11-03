"""Turn chat attachments into content blocks the model can read."""

import asyncio
import base64
from collections.abc import Iterable
from typing import Literal

from flow44.ai.core.messages import ContentBlock, FileContent, ImageContent, TextContent
from flow44.ai.core.provider import supports_pdf_input, supports_vision
from flow44.config import settings
from flow44.db.chat import ChatMessage, ChatRole
from flow44.db.uploads import Upload, get_uploads
from flow44.integrations.s3 import s3_storage

MAX_ATTACHMENTS_PER_MESSAGE = 10
_MAX_TEXT_CHARS = 100_000

_IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
# An allowlist, not text/*: uploads are served from our origin, so text/html would be stored XSS.
_TEXT_TYPES = frozenset({"text/plain", "text/csv", "text/markdown", "text/tab-separated-values", "application/json"})

AttachmentKind = Literal["image", "pdf", "text"]


def attachment_kind(content_type: str) -> AttachmentKind | None:
    if content_type in _IMAGE_TYPES:
        return "image"
    if content_type == "application/pdf":
        return "pdf"
    if content_type in _TEXT_TYPES:
        return "text"
    return None


def unsupported_reason(uploads: Iterable[Upload], model: str | None) -> str | None:
    kinds = {attachment_kind(u.content_type) for u in uploads}
    if "image" in kinds and not supports_vision(model):
        return "The selected model can't read images. Pick a model with vision support."
    if "pdf" in kinds and not supports_pdf_input(model):
        return "The selected model can't read PDFs. Pick another model or paste the text."
    return None


def attachment_placeholder(upload: Upload) -> str:
    return f"[attached {attachment_kind(upload.content_type) or 'file'}: {upload.name}]"


def _to_block(upload: Upload, body: bytes | None) -> ContentBlock:
    if body is None:
        return TextContent(text=f"[attachment no longer available: {upload.name}]")
    kind = attachment_kind(upload.content_type)
    if kind == "text":
        text = body.decode("utf-8", errors="replace")[:_MAX_TEXT_CHARS]
        return TextContent(text=f'<attachment name="{upload.name}">\n{text}\n</attachment>')
    data_uri = f"data:{upload.content_type};base64,{base64.b64encode(body).decode()}"
    return ImageContent.from_data_uri(data_uri) if kind == "image" else FileContent.from_data_uri(data_uri)


async def _blocks_for(uploads: list[Upload]) -> list[ContentBlock]:
    bodies = await asyncio.gather(*(s3_storage.read_upload(u.s3_key) for u in uploads))
    return [_to_block(u, body) for u, body in zip(uploads, bodies, strict=True)]


async def load_attachment_blocks(project_id: str, upload_ids: list[str]) -> list[ContentBlock]:
    return await _blocks_for(await get_uploads(project_id, upload_ids))


async def load_history_attachments(project_id: str, history: list[ChatMessage]) -> dict[str, list[ContentBlock]]:
    """Map each user message id to its attachment blocks; only the latest turns get the files themselves."""
    user_turns = [m for m in history if m.role == ChatRole.user]
    recent = {m.id for m in user_turns[-settings.AI_HISTORY_ATTACHMENT_TURNS :]}
    user_rows = [m for m in user_turns if m.attachment_ids]
    uploads = {u.id: u for u in await get_uploads(project_id, [i for m in user_rows for i in m.attachment_ids or []])}

    async def blocks(message: ChatMessage) -> list[ContentBlock]:
        rows = [uploads[i] for i in message.attachment_ids or [] if i in uploads]
        if message.id in recent:
            return await _blocks_for(rows)
        return [TextContent(text=attachment_placeholder(u)) for u in rows]

    loaded = await asyncio.gather(*(blocks(m) for m in user_rows))
    return {m.id: b for m, b in zip(user_rows, loaded, strict=True)}
