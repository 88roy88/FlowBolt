"""Project persistence using aiosqlite (raw SQL, no ORM)."""

from __future__ import annotations

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


async def delete_project(project_id: str) -> None:
    """Delete a project and its chat messages (cascade)."""
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        await db.commit()
