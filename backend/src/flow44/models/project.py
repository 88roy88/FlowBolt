"""Project persistence using aiosqlite (raw SQL, no ORM)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

import aiosqlite

from flow44.config import settings

_DB_PATH: str = ""


def _get_db_path() -> str:
    global _DB_PATH  # noqa: PLW0603
    if not _DB_PATH:
        url = settings.DATABASE_URL
        # Strip the "sqlite:///" prefix
        _DB_PATH = url.removeprefix("sqlite:///")
    return _DB_PATH


@dataclass
class Project:
    id: str
    name: str
    session_id: str
    created_at: str
    updated_at: str
    summary: str = ""
    selected_model: str = ""
    data_source_id: str = ""
    data_source_context: str = ""
    data_sources: str = "[]"


# TODO: use Alembic, move to PG and SQLModel.
async def init_db() -> None:
    """Create tables if they do not already exist."""
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                session_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
            """
        )
        await db.commit()

    # Migration-safe: add summary column if it doesn't exist
    async with aiosqlite.connect(_get_db_path()) as db:
        try:
            await db.execute("ALTER TABLE projects ADD COLUMN summary TEXT DEFAULT ''")
            await db.commit()
        except Exception:  # noqa: S110 — column already exists
            pass

    # Migration-safe: add selected_model column if it doesn't exist
    async with aiosqlite.connect(_get_db_path()) as db:
        try:
            await db.execute("ALTER TABLE projects ADD COLUMN selected_model TEXT DEFAULT ''")
            await db.commit()
        except Exception:  # noqa: S110 — column already exists
            pass

    # Migration-safe: rename package_id → case_id → data_source_id
    for old, new in [("package_id", "case_id"), ("case_id", "data_source_id")]:
        async with aiosqlite.connect(_get_db_path()) as db:
            try:
                await db.execute(f"ALTER TABLE projects RENAME COLUMN {old} TO {new}")  # noqa: S608
                await db.commit()
            except Exception:  # noqa: S110
                pass
    async with aiosqlite.connect(_get_db_path()) as db:
        try:
            await db.execute("ALTER TABLE projects ADD COLUMN data_source_id TEXT DEFAULT ''")
            await db.commit()
        except Exception:  # noqa: S110 — column already exists
            pass

    # Migration-safe: rename package_context → case_context → data_source_context
    for old, new in [("package_context", "case_context"), ("case_context", "data_source_context")]:
        async with aiosqlite.connect(_get_db_path()) as db:
            try:
                await db.execute(f"ALTER TABLE projects RENAME COLUMN {old} TO {new}")  # noqa: S608
                await db.commit()
            except Exception:  # noqa: S110
                pass
    async with aiosqlite.connect(_get_db_path()) as db:
        try:
            await db.execute("ALTER TABLE projects ADD COLUMN data_source_context TEXT DEFAULT ''")
            await db.commit()
        except Exception:  # noqa: S110 — column already exists
            pass

    # Migration-safe: rename cases → data_sources
    async with aiosqlite.connect(_get_db_path()) as db:
        try:
            await db.execute("ALTER TABLE projects RENAME COLUMN cases TO data_sources")
            await db.commit()
        except Exception:  # noqa: S110
            pass
    async with aiosqlite.connect(_get_db_path()) as db:
        try:
            await db.execute("ALTER TABLE projects ADD COLUMN data_sources TEXT DEFAULT '[]'")
            await db.commit()
        except Exception:  # noqa: S110 — column already exists
            pass


async def create_project(name: str) -> Project:
    """Insert a new project and return it."""
    project = Project(
        id=str(uuid.uuid4()),
        name=name,
        session_id=str(uuid.uuid4()),
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            "INSERT INTO projects (id, name, session_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (project.id, project.name, project.session_id, project.created_at, project.updated_at),
        )
        await db.commit()
    return project


async def get_project(project_id: str) -> Project | None:
    """Fetch a single project by id."""
    async with aiosqlite.connect(_get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)) as cur:
            row = await cur.fetchone()
            if row is None:
                return None
            return Project(**dict(row))


async def get_project_by_session(session_id: str) -> Project | None:
    """Fetch a single project by session_id."""
    async with aiosqlite.connect(_get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM projects WHERE session_id = ?", (session_id,)) as cur:
            row = await cur.fetchone()
            if row is None:
                return None
            return Project(**dict(row))


async def list_projects() -> list[Project]:
    """Return all projects ordered by creation date (newest first)."""
    async with aiosqlite.connect(_get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM projects ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
            return [Project(**dict(r)) for r in rows]


async def update_project_summary(project_id: str, summary: str) -> None:
    """Update the summary field for a project."""
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            "UPDATE projects SET summary = ?, updated_at = ? WHERE id = ?",
            (summary, datetime.now(UTC).isoformat(), project_id),
        )
        await db.commit()


async def rename_project(project_id: str, name: str) -> None:
    """Update the name of a project."""
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            "UPDATE projects SET name = ?, updated_at = ? WHERE id = ?",
            (name, datetime.now(UTC).isoformat(), project_id),
        )
        await db.commit()


async def update_project_model(project_id: str, model: str) -> None:
    """Update the selected_model field for a project."""
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            "UPDATE projects SET selected_model = ?, updated_at = ? WHERE id = ?",
            (model, datetime.now(UTC).isoformat(), project_id),
        )
        await db.commit()


async def update_project_data_source(project_id: str, data_source_id: str, data_source_context: str) -> None:
    """Update the data_source_id and data_source_context fields for a project."""
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            "UPDATE projects SET data_source_id = ?, data_source_context = ?, updated_at = ? WHERE id = ?",
            (data_source_id, data_source_context, datetime.now(UTC).isoformat(), project_id),
        )
        await db.commit()


async def update_project_data_sources(project_id: str, data_sources: list[dict[str, Any]]) -> None:
    """Update the data_sources column (JSON array) for a project."""
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            "UPDATE projects SET data_sources = ?, updated_at = ? WHERE id = ?",
            (json.dumps(data_sources), datetime.now(UTC).isoformat(), project_id),
        )
        await db.commit()


async def get_project_data_sources(project_id: str) -> list[dict[str, Any]]:
    """Read the data_sources column, falling back to single data_source_id/data_source_context."""
    async with aiosqlite.connect(_get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT data_sources, data_source_id, data_source_context FROM projects WHERE id = ?", (project_id,)
        ) as cur:
            row = await cur.fetchone()
            if row is None:
                return []
            raw = row["data_sources"]
            if raw and raw != "[]":
                try:
                    return cast(list[dict[str, Any]], json.loads(raw))
                except (json.JSONDecodeError, TypeError):
                    pass
            # Fallback: synthesize from single-source columns
            dsid = row["data_source_id"]
            dsctx = row["data_source_context"]
            if dsid:
                try:
                    ctx = json.loads(dsctx) if dsctx else {}
                except (json.JSONDecodeError, TypeError):
                    ctx = {}
                ctx["data_source_id"] = dsid
                return [ctx]
            return []


async def delete_project(project_id: str) -> None:
    """Delete a project and its chat messages (cascade)."""
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        await db.commit()
