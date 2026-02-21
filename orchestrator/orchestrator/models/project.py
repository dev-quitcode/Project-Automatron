"""Project SQLite models and CRUD operations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

# Module-level DB path (set during init)
_db_path: str = ""


async def init_db(db_path: str) -> None:
    """Initialize the project database, creating tables if needed."""
    global _db_path
    _db_path = db_path

    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        # Enable WAL mode for better concurrent read performance
        await db.execute("PRAGMA journal_mode=WAL")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PLANNING',
                plan_md TEXT,
                stack_config_json TEXT,
                container_id TEXT,
                port INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                phase TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS task_logs (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                task_index INTEGER NOT NULL,
                task_text TEXT,
                status TEXT NOT NULL,
                cline_output TEXT,
                duration_s REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)

        await db.commit()
        logger.info("Database initialized: %s", db_path)


def _now() -> str:
    """Get current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


async def create_project(
    project_id: str, name: str, description: str
) -> dict[str, Any]:
    """Create a new project record."""
    now = _now()
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            """
            INSERT INTO projects (id, name, status, plan_md, created_at, updated_at)
            VALUES (?, ?, 'PLANNING', ?, ?, ?)
            """,
            (project_id, name, f"# {name}\n\n{description}", now, now),
        )
        await db.commit()

    return await get_project(project_id)  # type: ignore[return-value]


async def get_project(project_id: str) -> dict[str, Any] | None:
    """Get a project by ID."""
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_all_projects() -> list[dict[str, Any]]:
    """Get all projects ordered by creation date."""
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM projects ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_project(project_id: str, **kwargs: Any) -> None:
    """Update project fields."""
    if not kwargs:
        return

    kwargs["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [project_id]

    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            f"UPDATE projects SET {set_clause} WHERE id = ?",
            values,
        )
        await db.commit()


async def update_project_plan(project_id: str, plan_md: str) -> None:
    """Update the PLAN.md content for a project."""
    await update_project(project_id, plan_md=plan_md)


async def update_project_status(project_id: str, status: str) -> None:
    """Update project status."""
    await update_project(project_id, status=status)


async def update_project_container(
    project_id: str, container_id: str, port: int
) -> None:
    """Update container info for a project."""
    await update_project(project_id, container_id=container_id, port=port)


# ── Chat Messages ───────────────────────────────────────────────────────


async def save_chat_message(
    message_id: str, project_id: str, role: str, content: str
) -> None:
    """Save a chat message."""
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            """
            INSERT INTO chat_messages (id, project_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (message_id, project_id, role, content, _now()),
        )
        await db.commit()


async def get_chat_messages(project_id: str) -> list[dict[str, Any]]:
    """Get all chat messages for a project."""
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM chat_messages WHERE project_id = ? ORDER BY created_at",
            (project_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ── Task Logs ───────────────────────────────────────────────────────────


async def save_task_log(
    log_id: str,
    session_id: str,
    task_index: int,
    task_text: str,
    status: str,
    cline_output: str,
    duration_s: float,
) -> None:
    """Save a task execution log."""
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            """
            INSERT INTO task_logs
                (id, session_id, task_index, task_text, status, cline_output, duration_s, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (log_id, session_id, task_index, task_text, status, cline_output, duration_s, _now()),
        )
        await db.commit()
