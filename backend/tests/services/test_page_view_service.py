from unittest.mock import AsyncMock, MagicMock, patch

from flow44.db.page_view import PageViewSource
from flow44.services.page_view_service import record_page_view


async def test_record_page_view_failure_does_not_raise():
    with (
        patch("flow44.services.page_view_service.increment_page_views", AsyncMock(side_effect=RuntimeError("db down"))),
        patch("flow44.services.page_view_service.log_bi_event") as bi_event,
    ):
        await record_page_view(MagicMock(id="proj-1"), PageViewSource.production, can_write=False)

    bi_event.assert_not_called()
