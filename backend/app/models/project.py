"""Project persistence using aiosqlite (raw SQL, no ORM)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite

from app.config import settings

_DB_PATH: str = ""


def _get_db_path() -> str:
    global _DB_PATH
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
    package_id: str = ""
    package_context: str = ""
    cases: str = "[]"


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
        except Exception:
            pass  # Column already exists

    # Migration-safe: add selected_model column if it doesn't exist
    async with aiosqlite.connect(_get_db_path()) as db:
        try:
            await db.execute("ALTER TABLE projects ADD COLUMN selected_model TEXT DEFAULT ''")
            await db.commit()
        except Exception:
            pass  # Column already exists

    # Migration-safe: add package_id column if it doesn't exist
    async with aiosqlite.connect(_get_db_path()) as db:
        try:
            await db.execute("ALTER TABLE projects ADD COLUMN package_id TEXT DEFAULT ''")
            await db.commit()
        except Exception:
            pass  # Column already exists

    # Migration-safe: add package_context column if it doesn't exist
    async with aiosqlite.connect(_get_db_path()) as db:
        try:
            await db.execute("ALTER TABLE projects ADD COLUMN package_context TEXT DEFAULT ''")
            await db.commit()
        except Exception:
            pass  # Column already exists

    # Migration-safe: add cases column if it doesn't exist
    async with aiosqlite.connect(_get_db_path()) as db:
        try:
            await db.execute("ALTER TABLE projects ADD COLUMN cases TEXT DEFAULT '[]'")
            await db.commit()
        except Exception:
            pass  # Column already exists


async def create_project(name: str) -> Project:
    """Insert a new project and return it."""
    project = Project(
        id=str(uuid.uuid4()),
        name=name,
        session_id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
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
            (summary, datetime.now(timezone.utc).isoformat(), project_id),
        )
        await db.commit()


async def rename_project(project_id: str, name: str) -> None:
    """Update the name of a project."""
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            "UPDATE projects SET name = ?, updated_at = ? WHERE id = ?",
            (name, datetime.now(timezone.utc).isoformat(), project_id),
        )
        await db.commit()


async def update_project_model(project_id: str, model: str) -> None:
    """Update the selected_model field for a project."""
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            "UPDATE projects SET selected_model = ?, updated_at = ? WHERE id = ?",
            (model, datetime.now(timezone.utc).isoformat(), project_id),
        )
        await db.commit()


async def update_project_package(project_id: str, package_id: str, package_context: str) -> None:
    """Update the package_id and package_context fields for a project."""
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            "UPDATE projects SET package_id = ?, package_context = ?, updated_at = ? WHERE id = ?",
            (package_id, package_context, datetime.now(timezone.utc).isoformat(), project_id),
        )
        await db.commit()


async def update_project_cases(project_id: str, cases: list[dict]) -> None:
    """Update the cases column (JSON array) for a project."""
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            "UPDATE projects SET cases = ?, updated_at = ? WHERE id = ?",
            (json.dumps(cases), datetime.now(timezone.utc).isoformat(), project_id),
        )
        await db.commit()


async def get_project_cases(project_id: str) -> list[dict]:
    """Read the cases column, falling back to old package_id/package_context for backward compat."""
    async with aiosqlite.connect(_get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT cases, package_id, package_context FROM projects WHERE id = ?", (project_id,)) as cur:
            row = await cur.fetchone()
            if row is None:
                return []
            cases_raw = row["cases"]
            if cases_raw and cases_raw != "[]":
                try:
                    return json.loads(cases_raw)
                except (json.JSONDecodeError, TypeError):
                    pass
            # Backward compat: synthesize from old columns
            pkg_id = row["package_id"]
            pkg_ctx = row["package_context"]
            if pkg_id:
                try:
                    ctx = json.loads(pkg_ctx) if pkg_ctx else {}
                except (json.JSONDecodeError, TypeError):
                    ctx = {}
                ctx["package_id"] = pkg_id
                return [ctx]
            return []


async def delete_project(project_id: str) -> None:
    """Delete a project and its chat messages (cascade)."""
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        await db.commit()
