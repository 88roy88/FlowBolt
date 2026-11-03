"""Tests for page-view counting using a real temporary Postgres database."""

from flow44.db.page_view import PageViewSource, increment_page_views, list_page_view_counts
from flow44.db.project import create_project, delete_project


class TestPageViews:
    async def test_increments_the_column_for_the_source(self, test_db):
        app_a = await create_project("A", user_id="test-user")
        app_b = await create_project("B", user_id="test-user")
        await increment_page_views(app_a.id, PageViewSource.production)
        await increment_page_views(app_a.id, PageViewSource.production)
        await increment_page_views(app_a.id, PageViewSource.preview)
        await increment_page_views(app_b.id, PageViewSource.preview)

        counts = await list_page_view_counts()

        assert {pid: (c.production_views, c.preview_views) for pid, c in counts.items()} == {
            app_a.id: (2, 1),
            app_b.id: (0, 1),
        }

    async def test_no_views_returns_empty(self, test_db):
        assert await list_page_view_counts() == {}

    async def test_counts_are_deleted_with_project(self, test_db):
        project = await create_project("A", user_id="test-user")
        await increment_page_views(project.id, PageViewSource.preview)

        await delete_project(project.id)

        assert await list_page_view_counts() == {}
