from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flow44.ai.attachments import load_history_attachments, unsupported_reason
from flow44.ai.core.messages import FileContent, ImageContent, TextContent
from flow44.config import settings
from flow44.db.chat import ChatMessage, ChatRole
from flow44.db.uploads import Upload, UploadKind


def _upload(name: str, content_type: str) -> Upload:
    return Upload(
        project_id="p",
        kind=UploadKind.attachment,
        name=name,
        s3_key=f"key-{name}",
        content_type=content_type,
        size_bytes=1,
        created_by="u",
    )


def _user(content: str, uploads: list[Upload]) -> ChatMessage:
    return ChatMessage(
        project_id="p", role=ChatRole.user, content=content, attachment_ids=[u.id for u in uploads] or None
    )


@pytest.mark.asyncio
async def test_only_the_latest_turns_send_files_and_older_ones_get_placeholders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AI_HISTORY_ATTACHMENT_TURNS", 2)
    old, shot, doc, notes = (
        _upload("old.png", "image/png"),
        _upload("shot.png", "image/png"),
        _upload("spec.pdf", "application/pdf"),
        _upload("notes.txt", "text/plain"),
    )
    history = [_user("first", [old]), _user("second", []), _user("third", [shot, doc, notes])]
    s3 = MagicMock()
    s3.read_upload = AsyncMock(side_effect=lambda key: b"body:" + key.encode())

    with (
        patch("flow44.ai.attachments.get_uploads", AsyncMock(return_value=[old, shot, doc, notes])),
        patch("flow44.ai.attachments.s3_storage", s3),
    ):
        blocks = await load_history_attachments("p", history)

    assert blocks[history[0].id] == [TextContent(text="[attached image: old.png]")]
    assert history[1].id not in blocks
    image, pdf, text = blocks[history[2].id]
    assert isinstance(image, ImageContent)
    assert image.image_url["url"] == "data:image/png;base64," + base64.b64encode(b"body:key-shot.png").decode()
    assert isinstance(pdf, FileContent)
    assert pdf.file["file_data"].startswith("data:application/pdf;base64,")
    assert text == TextContent(text='<attachment name="notes.txt">\nbody:key-notes.txt\n</attachment>')
    assert sorted(c.args[0] for c in s3.read_upload.await_args_list) == [
        "key-notes.txt",
        "key-shot.png",
        "key-spec.pdf",
    ]


@pytest.mark.asyncio
async def test_a_file_missing_from_storage_becomes_a_note() -> None:
    shot = _upload("shot.png", "image/png")
    history = [_user("hi", [shot])]
    s3 = MagicMock()
    s3.read_upload = AsyncMock(return_value=None)

    with (
        patch("flow44.ai.attachments.get_uploads", AsyncMock(return_value=[shot])),
        patch("flow44.ai.attachments.s3_storage", s3),
    ):
        blocks = await load_history_attachments("p", history)

    assert blocks[history[0].id] == [TextContent(text="[attachment no longer available: shot.png]")]


def test_unsupported_reason_checks_each_kind_against_the_model() -> None:
    image, pdf, text = (
        _upload("a.png", "image/png"),
        _upload("b.pdf", "application/pdf"),
        _upload("c.txt", "text/plain"),
    )

    with (
        patch("flow44.ai.attachments.supports_vision", return_value=False),
        patch("flow44.ai.attachments.supports_pdf_input", return_value=False),
    ):
        assert unsupported_reason([text], "m") is None
        assert "images" in (unsupported_reason([text, image], "m") or "")
        assert "PDFs" in (unsupported_reason([pdf], "m") or "")
