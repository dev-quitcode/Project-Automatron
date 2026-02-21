"""WebSocket (Socket.IO) event handlers."""

from __future__ import annotations

import logging

from orchestrator.main import sio

logger = logging.getLogger(__name__)


@sio.on("connect")
async def on_connect(sid: str, environ: dict) -> None:
    """Handle new WebSocket connection."""
    query = environ.get("QUERY_STRING", "")
    logger.info("Client connected: %s (query: %s)", sid, query)
    # Extract projectId from query string and join room
    params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
    project_id = params.get("projectId")
    if project_id:
        sio.enter_room(sid, f"project:{project_id}")
        logger.info("Client %s joined room project:%s", sid, project_id)


@sio.on("disconnect")
async def on_disconnect(sid: str) -> None:
    """Handle WebSocket disconnection."""
    logger.info("Client disconnected: %s", sid)


@sio.on("chat:message")
async def on_chat_message(sid: str, data: dict) -> None:
    """Handle chat message from user to Architect."""
    project_id = data.get("projectId")
    text = data.get("text", "")
    logger.info("Chat message for project %s: %s", project_id, text[:100])
    # TODO: Forward message to LangGraph architect node
    # For now, echo back a placeholder
    await sio.emit(
        "architect:message",
        {"content": f"[Architect] Received: {text}", "streaming": False},
        room=f"project:{project_id}",
    )


# ── Helper functions for emitting events from graph nodes ───────────────


async def emit_architect_message(project_id: str, content: str, streaming: bool = True) -> None:
    """Emit architect message to project room."""
    await sio.emit(
        "architect:message",
        {"content": content, "streaming": streaming},
        room=f"project:{project_id}",
    )


async def emit_builder_log(project_id: str, line: str) -> None:
    """Emit builder log line to project room."""
    await sio.emit(
        "builder:log",
        {"line": line},
        room=f"project:{project_id}",
    )


async def emit_status_update(project_id: str, phase: str, progress: dict) -> None:
    """Emit status update to project room."""
    await sio.emit(
        "status:update",
        {"phase": phase, "progress": progress},
        room=f"project:{project_id}",
    )


async def emit_human_required(project_id: str, reason: str) -> None:
    """Emit human intervention alert to project room."""
    await sio.emit(
        "human:required",
        {"reason": reason},
        room=f"project:{project_id}",
    )


async def emit_plan_updated(project_id: str, plan_md: str) -> None:
    """Emit plan updated event to project room."""
    await sio.emit(
        "plan:updated",
        {"plan_md": plan_md},
        room=f"project:{project_id}",
    )
