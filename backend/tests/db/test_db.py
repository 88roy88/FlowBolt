"""Tests for db/ CRUD operations using real temporary SQLite."""

from __future__ import annotations

from flow44.db.chat import get_messages, save_message
from flow44.db.events import clear_events, emit_event, get_events
from flow44.db.project import (
    create_project,
    delete_project,
    get_project,
    get_project_data_sources,
    list_all_projects,
    rename_project,
    update_project_data_source,
    update_project_data_sources,
    update_project_model,
    update_project_published_url,
    update_project_summary,
)

# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


class TestProjectCRUD:
    async def test_create_project(self, test_db):
        project = await create_project("My App", user_id="test-user")
        assert project.name == "My App"
        assert project.id
        assert project.created_at
        assert project.summary == ""

    async def test_get_project(self, test_db):
        created = await create_project("Test", user_id="test-user")
        fetched = await get_project(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "Test"

    async def test_get_project_not_found(self, test_db):
        result = await get_project("nonexistent-id")
        assert result is None

    async def test_list_projects_empty(self, test_db):
        projects = await list_all_projects()
        assert projects == []

    async def test_list_projects_ordered_newest_first(self, test_db):
        p1 = await create_project("First", user_id="test-user")
        p2 = await create_project("Second", user_id="test-user")
        p3 = await create_project("Third", user_id="test-user")

        projects = await list_all_projects()
        assert len(projects) == 3
        assert projects[0].id == p3.id
        assert projects[2].id == p1.id

    async def test_rename_project(self, test_db):
        project = await create_project("Old Name", user_id="test-user")
        await rename_project(project.id, "New Name")

        fetched = await get_project(project.id)
        assert fetched is not None
        assert fetched.name == "New Name"
        assert fetched.updated_at > project.updated_at

    async def test_update_project_summary(self, test_db):
        project = await create_project("App", user_id="test-user")
        await update_project_summary(project.id, "A cool app")

        fetched = await get_project(project.id)
        assert fetched is not None
        assert fetched.summary == "A cool app"

    async def test_update_project_model(self, test_db):
        project = await create_project("App", user_id="test-user")
        await update_project_model(project.id, "claude-sonnet-4-6")

        fetched = await get_project(project.id)
        assert fetched is not None
        assert fetched.selected_model == "claude-sonnet-4-6"

    async def test_update_project_data_sources(self, test_db):
        project = await create_project("App", user_id="test-user")
        ds = [{"data_source_id": "ds1", "schema": "..."}]
        await update_project_data_sources(project.id, ds)

        result = await get_project_data_sources(project.id)
        assert len(result) == 1
        assert result[0]["data_source_id"] == "ds1"

    async def test_get_data_sources_fallback_to_single(self, test_db):
        project = await create_project("App", user_id="test-user")
        await update_project_data_source(project.id, "ds-legacy", '{"field": "value"}')

        result = await get_project_data_sources(project.id)
        assert len(result) == 1
        assert result[0]["data_source_id"] == "ds-legacy"
        assert result[0]["field"] == "value"

    async def test_get_data_sources_empty(self, test_db):
        project = await create_project("App", user_id="test-user")
        result = await get_project_data_sources(project.id)
        assert result == []

    async def test_delete_project(self, test_db):
        project = await create_project("To Delete", user_id="test-user")
        await delete_project(project.id)

        fetched = await get_project(project.id)
        assert fetched is None

    async def test_update_project_published_url(self, test_db):
        project = await create_project("App", user_id="test-user")
        url = "https://s3.amazonaws.com/my-bucket/project-id/index.html"
        await update_project_published_url(project.id, url)

        fetched = await get_project(project.id)
        assert fetched is not None
        assert fetched.published_url == url
        assert fetched.updated_at > project.updated_at

    async def test_delete_project_cascades_messages(self, test_db):
        project = await create_project("App", user_id="test-user")
        await save_message(project.id, "user", "Hello")
        await save_message(project.id, "assistant", "Hi!")

        await delete_project(project.id)

        messages = await get_messages(project.id)
        assert messages == []


# ---------------------------------------------------------------------------
# ChatMessage CRUD
# ---------------------------------------------------------------------------


class TestChatMessageCRUD:
    async def test_save_and_get_messages(self, test_db):
        project = await create_project("App", user_id="test-user")
        m1 = await save_message(project.id, "user", "Hello")
        m2 = await save_message(project.id, "assistant", "Hi there!")

        messages = await get_messages(project.id)
        assert len(messages) == 2
        assert messages[0].id == m1.id
        assert messages[0].role == "user"
        assert messages[0].content == "Hello"
        assert messages[1].id == m2.id
        assert messages[1].role == "assistant"

    async def test_get_messages_empty(self, test_db):
        project = await create_project("App", user_id="test-user")
        messages = await get_messages(project.id)
        assert messages == []

    async def test_messages_isolated_by_project(self, test_db):
        p1 = await create_project("App 1", user_id="test-user")
        p2 = await create_project("App 2", user_id="test-user")
        await save_message(p1.id, "user", "For project 1")
        await save_message(p2.id, "user", "For project 2")

        msgs1 = await get_messages(p1.id)
        msgs2 = await get_messages(p2.id)
        assert len(msgs1) == 1
        assert len(msgs2) == 1
        assert msgs1[0].content == "For project 1"
        assert msgs2[0].content == "For project 2"


# ---------------------------------------------------------------------------
# AgentEvent CRUD
# ---------------------------------------------------------------------------


class TestAgentEventCRUD:
    async def test_emit_and_get_events(self, test_db):
        project = await create_project("App", user_id="test-user")
        await emit_event(project.id, {"type": "phase", "phase": "designing"}, notify=False)
        await emit_event(project.id, {"type": "phase", "phase": "executing"}, notify=False)

        events = await get_events(project.id)
        assert len(events) == 2
        assert events[0].event_type == "phase"
        assert events[0].payload["phase"] == "designing"
        assert events[1].payload["phase"] == "executing"

    async def test_get_events_after_id(self, test_db):
        project = await create_project("App", user_id="test-user")
        await emit_event(project.id, {"type": "phase", "phase": "designing"}, notify=False)
        await emit_event(project.id, {"type": "phase", "phase": "executing"}, notify=False)

        events = await get_events(project.id)
        first_id = events[0].id

        events_after = await get_events(project.id, after_id=first_id)
        assert len(events_after) == 1
        assert events_after[0].payload["phase"] == "executing"

    async def test_get_events_empty(self, test_db):
        project = await create_project("App", user_id="test-user")
        events = await get_events(project.id)
        assert events == []

    async def test_clear_events(self, test_db):
        project = await create_project("App", user_id="test-user")
        await emit_event(project.id, {"type": "phase", "phase": "designing"}, notify=False)
        await emit_event(project.id, {"type": "action_complete"}, notify=False)

        await clear_events(project.id)

        events = await get_events(project.id)
        assert events == []

    async def test_events_isolated_by_project(self, test_db):
        p1 = await create_project("App 1", user_id="test-user")
        p2 = await create_project("App 2", user_id="test-user")
        await emit_event(p1.id, {"type": "phase", "phase": "designing"}, notify=False)
        await emit_event(p2.id, {"type": "action_complete"}, notify=False)

        events1 = await get_events(p1.id)
        events2 = await get_events(p2.id)
        assert len(events1) == 1
        assert len(events2) == 1
        assert events1[0].payload["phase"] == "designing"
        assert events2[0].payload["type"] == "action_complete"

    async def test_event_payload_preserves_complex_json(self, test_db):
        project = await create_project("App", user_id="test-user")
        payload = {
            "type": "task_list",
            "tasks": [
                {"id": "t1", "name": "Create Header", "status": "pending"},
                {"id": "t2", "name": "Create Footer", "status": "pending"},
            ],
        }
        await emit_event(project.id, payload, notify=False)

        events = await get_events(project.id)
        assert len(events) == 1
        assert len(events[0].payload["tasks"]) == 2
        assert events[0].payload["tasks"][0]["name"] == "Create Header"
