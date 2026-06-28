"""Tests for db/ CRUD operations using real temporary SQLite."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlmodel import select

from flow44.config import settings
from flow44.db import database
from flow44.db.chat import get_messages, save_message
from flow44.db.events import clear_events, emit_event, get_events
from flow44.db.heartbeat import (
    AgentRunHeartbeat,
    get_heartbeat,
    is_run_active,
    reap_stale_runs,
    touch_heartbeat,
    try_claim_run,
)
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
        handle = "my-custom-slug"
        await update_project_published_url(project.id, handle)

        fetched = await get_project(project.id)
        assert fetched is not None
        assert fetched.published_url == handle
        assert fetched.published_at is not None
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


async def _seed_heartbeat(project_id: str, *, age_seconds: float = 0.0) -> None:
    """Insert a heartbeat row directly with an explicit age."""
    async with database.async_session() as session:
        session.add(
            AgentRunHeartbeat(
                project_id=project_id,
                beat_at=datetime.now(UTC) - timedelta(seconds=age_seconds),
            )
        )
        await session.commit()


class TestRunLiveness:
    async def test_emit_event_populates_created_at(self, test_db):
        project = await create_project("App", user_id="test-user")
        await emit_event(project.id, {"type": "phase", "phase": "designing"}, notify=False)

        events = await get_events(project.id)
        assert events[0].created_at is not None

    async def test_is_run_active_true_for_fresh_heartbeat(self, test_db):
        project = await create_project("App", user_id="test-user")
        await touch_heartbeat(project.id)

        assert await is_run_active(project.id) is True

    async def test_is_run_active_false_without_heartbeat(self, test_db):
        project = await create_project("App", user_id="test-user")

        assert await is_run_active(project.id) is False

    async def test_is_run_active_false_with_stale_heartbeat(self, test_db):
        project = await create_project("App", user_id="test-user")
        await _seed_heartbeat(project.id, age_seconds=settings.AGENT_RUN_STALE_TIMEOUT + 10)

        assert await is_run_active(project.id) is False

    async def test_reap_stale_runs_closes_stale_and_is_idempotent(self, test_db):
        project = await create_project("App", user_id="test-user")
        await _seed_heartbeat(project.id, age_seconds=settings.AGENT_RUN_STALE_TIMEOUT + 10)

        assert await reap_stale_runs() == 1
        errors = [e for e in await get_events(project.id) if e.payload.get("type") == "error"]
        assert len(errors) == 1
        assert errors[0].payload["message"] == "Agent run was interrupted"
        assert await get_heartbeat(project.id) is None

        # Second sweep is a no-op — the heartbeat is already cleared.
        assert await reap_stale_runs() == 0
        assert len([e for e in await get_events(project.id) if e.payload.get("type") == "error"]) == 1

    async def test_reap_stale_runs_keeps_fresh_run(self, test_db):
        project = await create_project("App", user_id="test-user")
        await touch_heartbeat(project.id)

        assert await reap_stale_runs() == 0
        assert [e for e in await get_events(project.id) if e.payload.get("type") == "error"] == []
        assert await get_heartbeat(project.id) is not None

    async def test_reap_stale_runs_skips_run_refreshed_before_sweep(self, test_db):
        project = await create_project("App", user_id="test-user")
        await _seed_heartbeat(project.id, age_seconds=settings.AGENT_RUN_STALE_TIMEOUT + 10)
        # A new run reclaims/refreshes the lock before the sweep deletes it.
        await touch_heartbeat(project.id)

        assert await reap_stale_runs() == 0
        assert [e for e in await get_events(project.id) if e.payload.get("type") == "error"] == []
        assert await get_heartbeat(project.id) is not None

    async def test_reap_stale_runs_reaps_only_stale_rows(self, test_db):
        stale = await create_project("Stale", user_id="test-user")
        fresh = await create_project("Fresh", user_id="test-user")
        await _seed_heartbeat(stale.id, age_seconds=settings.AGENT_RUN_STALE_TIMEOUT + 10)
        await touch_heartbeat(fresh.id)

        assert await reap_stale_runs() == 1
        assert await get_heartbeat(stale.id) is None
        assert await get_heartbeat(fresh.id) is not None
        assert [e for e in await get_events(fresh.id) if e.payload.get("type") == "error"] == []

    async def test_try_claim_run_claims_when_absent(self, test_db):
        project = await create_project("App", user_id="test-user")

        assert await try_claim_run(project.id) is True
        assert await is_run_active(project.id) is True

    async def test_try_claim_run_rejects_when_fresh(self, test_db):
        project = await create_project("App", user_id="test-user")
        await touch_heartbeat(project.id)

        assert await try_claim_run(project.id) is False

    async def test_try_claim_run_claims_when_stale(self, test_db):
        project = await create_project("App", user_id="test-user")
        await _seed_heartbeat(project.id, age_seconds=settings.AGENT_RUN_STALE_TIMEOUT + 10)

        assert await try_claim_run(project.id) is True
        assert await is_run_active(project.id) is True

    async def test_touch_heartbeat_upserts_single_row(self, test_db):
        project = await create_project("App", user_id="test-user")
        await touch_heartbeat(project.id)
        first = await get_heartbeat(project.id)
        assert first is not None
        await touch_heartbeat(project.id)

        async with database.async_session() as session:
            rows = (await session.execute(select(AgentRunHeartbeat))).scalars().all()
        assert len([r for r in rows if r.project_id == project.id]) == 1

    async def test_delete_project_cascades_heartbeat(self, test_db):
        project = await create_project("App", user_id="test-user")
        await touch_heartbeat(project.id)

        await delete_project(project.id)

        assert await get_heartbeat(project.id) is None
