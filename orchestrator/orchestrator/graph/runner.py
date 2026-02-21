"""Graph runner — manages LangGraph execution sessions.

Provides an async interface for the REST API to start, resume, and stop
LangGraph graph runs for projects. Each project gets its own thread_id.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from langchain_core.messages import HumanMessage

from orchestrator.config import settings
from orchestrator.graph.graph import compile_graph
from orchestrator.graph.state import AutomatronState
from orchestrator.models.project import (
    get_project,
    update_project_status,
    update_project_plan,
    update_project_container,
)
from orchestrator.models.session import create_session, end_session
from orchestrator.api.websocket import (
    emit_status_update,
    emit_architect_message,
    emit_plan_updated,
    emit_human_required,
)

logger = logging.getLogger(__name__)

# ── Active run tracking ─────────────────────────────────────────────────
_active_runs: dict[str, asyncio.Task] = {}
_compiled_graph = None


def _get_graph():
    """Lazily compile the graph once."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = compile_graph()
    return _compiled_graph


def _make_thread_config(project_id: str) -> dict[str, Any]:
    """Create a LangGraph config with a thread_id scoped to the project."""
    return {"configurable": {"thread_id": f"automatron:{project_id}"}}


async def _run_graph(project_id: str, initial_state: dict[str, Any]) -> None:
    """Internal: execute the graph in a background task.

    This function is invoked via asyncio.create_task so it doesn't block
    the API endpoint.  It streams events back via WebSocket helpers.
    """
    graph = _get_graph()
    config = _make_thread_config(project_id)
    session_id = str(uuid.uuid4())

    try:
        await create_session(session_id, project_id, config["configurable"]["thread_id"], "PLANNING")
        await update_project_status(project_id, "planning")
        await emit_status_update(project_id, "planning", {})

        # Run the graph — this blocks until END or interrupt()
        # LangGraph's async invoke handles the internal loop.
        final_state = await graph.ainvoke(initial_state, config)

        # Check final phase
        phase = final_state.get("phase", "COMPLETED")

        if phase == "COMPLETED":
            await update_project_status(project_id, "completed")
            await emit_status_update(project_id, "completed", {
                "total": final_state.get("total_tasks", 0),
                "completed": final_state.get("completed_tasks", 0),
            })
        elif final_state.get("requires_human"):
            await update_project_status(project_id, "paused")
            await emit_human_required(
                project_id,
                final_state.get("human_intervention_reason", "Review required"),
            )
        elif phase == "FROZEN":
            await update_project_status(project_id, "frozen")
            await emit_status_update(project_id, "frozen", {})

        # Persist plan if updated
        plan_md = final_state.get("plan_md", "")
        if plan_md:
            await update_project_plan(project_id, plan_md)
            await emit_plan_updated(project_id, plan_md)

        # Persist container info if created
        container_id = final_state.get("container_id", "")
        container_port = final_state.get("container_port", 0)
        if container_id:
            await update_project_container(project_id, container_id, container_port)

    except asyncio.CancelledError:
        logger.info("Graph run cancelled for project %s", project_id)
        await update_project_status(project_id, "paused")
        await emit_status_update(project_id, "paused", {})
    except Exception:
        logger.exception("Graph run failed for project %s", project_id)
        await update_project_status(project_id, "error")
        await emit_status_update(project_id, "error", {})
    finally:
        await end_session(session_id)
        _active_runs.pop(project_id, None)


async def start_project(project_id: str) -> dict[str, str]:
    """Start a new graph run for a project.

    Returns immediately; the graph runs in the background.
    """
    if project_id in _active_runs:
        return {"status": "already_running", "project_id": project_id}

    project = await get_project(project_id)
    if not project:
        return {"status": "not_found", "project_id": project_id}

    # Build initial state
    initial_state: dict[str, Any] = {
        "project_id": project_id,
        "project_name": project["name"],
        "plan_md": project.get("plan_md", ""),
        "stack_config": {},
        "current_task_index": 0,
        "current_task_text": "",
        "total_tasks": 0,
        "completed_tasks": 0,
        "messages": [
            HumanMessage(content=project.get("plan_md", "")),
        ],
        "builder_status": "",
        "builder_output": "",
        "builder_error_detail": "",
        "escalation_count": 0,
        "escalation_history": [],
        "container_id": project.get("container_id", ""),
        "container_port": project.get("port", 0) or 0,
        "phase": "PLANNING",
        "requires_human": False,
        "human_intervention_reason": "",
    }

    task = asyncio.create_task(_run_graph(project_id, initial_state))
    _active_runs[project_id] = task

    return {"status": "started", "project_id": project_id}


async def resume_project(project_id: str, feedback: str | None = None) -> dict[str, str]:
    """Resume a paused graph run (after human review / interrupt).

    Sends the approval + optional feedback as an update to the checkpoint.
    """
    if project_id in _active_runs:
        return {"status": "already_running", "project_id": project_id}

    graph = _get_graph()
    config = _make_thread_config(project_id)

    # Get the latest checkpoint state
    state = await graph.aget_state(config)

    if not state or not state.values:
        return {"status": "no_checkpoint", "project_id": project_id}

    # Resume by updating state — clear human flag and add feedback message
    update: dict[str, Any] = {
        "requires_human": False,
        "human_intervention_reason": "",
    }
    if feedback:
        update["messages"] = [HumanMessage(content=f"[Human Feedback] {feedback}")]

    # Schedule the resumed run as a background task
    async def _resume():
        try:
            await update_project_status(project_id, "building")
            await emit_status_update(project_id, "building", {})

            final_state = await graph.ainvoke(update, config)

            phase = final_state.get("phase", "COMPLETED")
            if phase == "COMPLETED":
                await update_project_status(project_id, "completed")
                await emit_status_update(project_id, "completed", {})
            elif final_state.get("requires_human"):
                await update_project_status(project_id, "paused")
                await emit_human_required(
                    project_id,
                    final_state.get("human_intervention_reason", "Review required"),
                )

            plan_md = final_state.get("plan_md", "")
            if plan_md:
                await update_project_plan(project_id, plan_md)
                await emit_plan_updated(project_id, plan_md)

        except asyncio.CancelledError:
            await update_project_status(project_id, "paused")
        except Exception:
            logger.exception("Resume failed for project %s", project_id)
            await update_project_status(project_id, "error")
        finally:
            _active_runs.pop(project_id, None)

    task = asyncio.create_task(_resume())
    _active_runs[project_id] = task

    return {"status": "resumed", "project_id": project_id}


async def stop_project(project_id: str) -> dict[str, str]:
    """Cancel the active graph run for a project."""
    task = _active_runs.pop(project_id, None)
    if task:
        task.cancel()
        await update_project_status(project_id, "paused")
        return {"status": "stopped", "project_id": project_id}
    return {"status": "not_running", "project_id": project_id}


def is_running(project_id: str) -> bool:
    """Check if a project has an active graph run."""
    return project_id in _active_runs


async def get_checkpoints(project_id: str) -> list[dict[str, Any]]:
    """Get checkpoint history for a project (for time-travel UI)."""
    graph = _get_graph()
    config = _make_thread_config(project_id)

    checkpoints = []
    try:
        async for checkpoint in graph.aget_state_history(config):
            checkpoints.append({
                "config": checkpoint.config,
                "created_at": checkpoint.created_at,
                "parent_config": checkpoint.parent_config,
                "values_summary": {
                    "phase": checkpoint.values.get("phase", ""),
                    "current_task_index": checkpoint.values.get("current_task_index", 0),
                    "completed_tasks": checkpoint.values.get("completed_tasks", 0),
                    "total_tasks": checkpoint.values.get("total_tasks", 0),
                },
            })
    except Exception:
        logger.warning("Failed to get checkpoint history for %s", project_id)

    return checkpoints
