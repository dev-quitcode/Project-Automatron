"""Dynamic port allocator for project containers."""

from __future__ import annotations

import logging
import socket

import aiosqlite

from orchestrator.config import settings

logger = logging.getLogger(__name__)


class PortAllocator:
    """Allocates unique ports from a defined range for project containers.

    Stores allocations in the project SQLite database.
    """

    def __init__(self, start: int = 7000, end: int = 7999) -> None:
        self.start = start
        self.end = end
        self._db_path = settings.sqlite_db_path

    async def _ensure_table(self, db: aiosqlite.Connection) -> None:
        """Create port_allocations table if it doesn't exist."""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS port_allocations (
                project_id TEXT PRIMARY KEY,
                port INTEGER NOT NULL UNIQUE,
                allocated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

    async def allocate(self, project_id: str) -> int:
        """Allocate the first available port for a project.

        Args:
            project_id: Unique project identifier

        Returns:
            Allocated port number

        Raises:
            RuntimeError: If no ports are available
        """
        async with aiosqlite.connect(self._db_path) as db:
            await self._ensure_table(db)

            # Check if project already has a port
            cursor = await db.execute(
                "SELECT port FROM port_allocations WHERE project_id = ?",
                (project_id,),
            )
            row = await cursor.fetchone()
            if row:
                logger.info("Port %d already allocated for project %s", row[0], project_id[:8])
                return row[0]

            # Get all allocated ports
            cursor = await db.execute("SELECT port FROM port_allocations")
            allocated = {row[0] for row in await cursor.fetchall()}

            # Find first free port
            for port in range(self.start, self.end + 1):
                if port not in allocated and self._is_port_free(port):
                    await db.execute(
                        "INSERT INTO port_allocations (project_id, port) VALUES (?, ?)",
                        (project_id, port),
                    )
                    await db.commit()
                    logger.info("Allocated port %d for project %s", port, project_id[:8])
                    return port

            raise RuntimeError(
                f"No available ports in range {self.start}-{self.end}"
            )

    async def release(self, project_id: str) -> None:
        """Release the allocated port for a project."""
        async with aiosqlite.connect(self._db_path) as db:
            await self._ensure_table(db)
            await db.execute(
                "DELETE FROM port_allocations WHERE project_id = ?",
                (project_id,),
            )
            await db.commit()
            logger.info("Released port for project %s", project_id[:8])

    async def get_port(self, project_id: str) -> int | None:
        """Get the allocated port for a project, if any."""
        async with aiosqlite.connect(self._db_path) as db:
            await self._ensure_table(db)
            cursor = await db.execute(
                "SELECT port FROM port_allocations WHERE project_id = ?",
                (project_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    @staticmethod
    def _is_port_free(port: int) -> bool:
        """Check if a port is free on the host machine."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("127.0.0.1", port))
                return result != 0  # != 0 means port is free
        except OSError:
            return True
