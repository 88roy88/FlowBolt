import functools
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

import flow44.config


def _get_async_url() -> str:
    url = flow44.config.settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


@functools.lru_cache
def get_engine(url: str | None = None) -> AsyncEngine:
    async_url = url or _get_async_url()
    eng = create_async_engine(async_url, echo=False)

    # TODO: this is specific for SQLite, remove when migrating to Postgres
    @event.listens_for(eng.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_conn: Any, _connection_record: Any) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    return eng


@functools.lru_cache
def get_session_factory(url: str | None = None) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(url), class_=AsyncSession, expire_on_commit=False)


def async_session() -> AsyncSession:
    return get_session_factory()()


async def reset() -> None:
    if get_engine.cache_info().currsize > 0:
        await get_engine().dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


async def init_db() -> None:  # noqa: C901
    from sqlmodel import SQLModel  # noqa: PLC0415

    import flow44.db.chat  # noqa: F401, PLC0415
    import flow44.db.events  # noqa: F401, PLC0415
    import flow44.db.project  # noqa: F401, PLC0415

    def _ensure_sqlite_projects_columns(conn: Any) -> None:
        if conn.dialect.name != "sqlite":
            return

        table_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
        ).fetchone()
        if table_exists is None:
            return

        rows = conn.execute(text("PRAGMA table_info(projects)")).fetchall()
        existing = {str(row[1]) for row in rows}
        if "session_id" in existing:
            # Legacy schema used session_id/package_* columns. Rebuild to the new project_id-era schema.
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS projects__migrated (
                        id TEXT PRIMARY KEY NOT NULL,
                        name TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        summary TEXT NOT NULL DEFAULT '',
                        selected_model TEXT NOT NULL DEFAULT '',
                        data_source_id TEXT NOT NULL DEFAULT '',
                        data_source_context TEXT NOT NULL DEFAULT '',
                        data_sources JSON NOT NULL DEFAULT '[]'
                    )
                    """
                )
            )

            data_source_id_expr = (
                "CASE "
                "WHEN data_source_id IS NOT NULL AND data_source_id != '' THEN data_source_id "
                "WHEN package_id IS NOT NULL THEN package_id "
                "ELSE '' END"
                if "package_id" in existing
                else ("COALESCE(data_source_id, '')" if "data_source_id" in existing else "''")
            )
            data_source_context_expr = (
                "CASE "
                "WHEN data_source_context IS NOT NULL AND data_source_context != '' THEN data_source_context "
                "WHEN package_context IS NOT NULL THEN package_context "
                "ELSE '' END"
                if "package_context" in existing
                else ("COALESCE(data_source_context, '')" if "data_source_context" in existing else "''")
            )
            data_sources_expr = (
                "CASE "
                "WHEN data_sources IS NOT NULL AND data_sources != '' THEN data_sources "
                "WHEN cases IS NOT NULL AND cases != '' THEN cases "
                "ELSE '[]' END"
                if "cases" in existing
                else ("COALESCE(data_sources, '[]')" if "data_sources" in existing else "'[]'")
            )
            created_at_expr = "COALESCE(created_at, '')" if "created_at" in existing else "''"
            updated_at_expr = "COALESCE(updated_at, '')" if "updated_at" in existing else "''"
            summary_expr = "COALESCE(summary, '')" if "summary" in existing else "''"
            selected_model_expr = "COALESCE(selected_model, '')" if "selected_model" in existing else "''"

            conn.execute(  # noqa: S608
                text(
                    f"""
                    INSERT INTO projects__migrated (
                        id,
                        name,
                        created_at,
                        updated_at,
                        summary,
                        selected_model,
                        data_source_id,
                        data_source_context,
                        data_sources
                    )
                    SELECT
                        id,
                        name,
                        {created_at_expr},
                        {updated_at_expr},
                        {summary_expr},
                        {selected_model_expr},
                        {data_source_id_expr},
                        {data_source_context_expr},
                        {data_sources_expr}
                    FROM projects
                    """
                )
            )
            conn.execute(text("DROP TABLE projects"))
            conn.execute(text("ALTER TABLE projects__migrated RENAME TO projects"))
            return

        missing_columns = [
            ("data_source_id", "TEXT NOT NULL DEFAULT ''"),
            ("data_source_context", "TEXT NOT NULL DEFAULT ''"),
            ("data_sources", "JSON NOT NULL DEFAULT '[]'"),
        ]
        for column_name, column_sql in missing_columns:
            if column_name in existing:
                continue
            conn.execute(text(f"ALTER TABLE projects ADD COLUMN {column_name} {column_sql}"))

    def _ensure_sqlite_agent_events_columns(conn: Any) -> None:
        if conn.dialect.name != "sqlite":
            return

        table_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='agent_events'")
        ).fetchone()
        if table_exists is None:
            return

        rows = conn.execute(text("PRAGMA table_info(agent_events)")).fetchall()
        existing = {str(row[1]) for row in rows}

        # Legacy schema used `session_id` (NOT NULL). Rebuild table to remove that constraint
        # and keep only project_id-based schema expected by current SQLModel.
        if "session_id" in existing:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS agent_events__migrated (
                        id INTEGER PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        payload JSON NOT NULL DEFAULT '{}',
                        created_at TEXT
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO agent_events__migrated (id, project_id, event_type, payload, created_at)
                    SELECT
                        id,
                        CASE
                            WHEN project_id IS NOT NULL AND project_id != '' THEN project_id
                            WHEN session_id IS NOT NULL THEN session_id
                            ELSE ''
                        END,
                        event_type,
                        payload,
                        created_at
                    FROM agent_events
                    """
                )
            )
            conn.execute(text("DROP TABLE agent_events"))
            conn.execute(text("ALTER TABLE agent_events__migrated RENAME TO agent_events"))
        elif "project_id" not in existing:
            conn.execute(text("ALTER TABLE agent_events ADD COLUMN project_id TEXT NOT NULL DEFAULT ''"))

        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_events_project_id ON agent_events(project_id)"))

    async with get_engine().begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.run_sync(_ensure_sqlite_projects_columns)
        await conn.run_sync(_ensure_sqlite_agent_events_columns)
