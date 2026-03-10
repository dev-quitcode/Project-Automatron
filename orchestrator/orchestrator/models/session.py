"""Session models tracking graph execution sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import aiosqlite

from orchestrator.models import project as project_model


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_session(
    session_id: str,
    project_id: str,
    thread_id: str,
    phase: str,
) -> dict[str, Any]:
    async with aiosqlite.connect(project_model._db_path) as db:
        await db.execute(
            """
            INSERT INTO sessions (id, project_id, thread_id, phase, started_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, project_id, thread_id, phase, _now()),
        )
        await db.commit()

    return {
        "id": session_id,
        "project_id": project_id,
        "thread_id": thread_id,
        "phase": phase,
        "started_at": _now(),
    }


async def update_session_phase(session_id: str, phase: str) -> None:
    async with aiosqlite.connect(project_model._db_path) as db:
        await db.execute("UPDATE sessions SET phase = ? WHERE id = ?", (phase, session_id))
        await db.commit()


async def end_session(session_id: str) -> None:
    async with aiosqlite.connect(project_model._db_path) as db:
        await db.execute("UPDATE sessions SET ended_at = ? WHERE id = ?", (_now(), session_id))
        await db.commit()


async def get_sessions(project_id: str) -> list[dict[str, Any]]:
    async with aiosqlite.connect(project_model._db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM sessions WHERE project_id = ? ORDER BY started_at DESC",
            (project_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
