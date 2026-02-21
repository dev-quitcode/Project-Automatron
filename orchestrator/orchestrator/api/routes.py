"""REST API routes for project management."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from orchestrator.models.project import (
    create_project,
    get_all_projects,
    get_project,
    get_chat_messages,
    update_project_plan,
)
from orchestrator.models.session import get_sessions
from orchestrator.graph.runner import (
    start_project as runner_start,
    resume_project as runner_resume,
    stop_project as runner_stop,
    get_checkpoints,
)

router = APIRouter()


# ── Request / Response schemas ──────────────────────────────────────────


class CreateProjectRequest(BaseModel):
    name: str
    description: str


class UpdatePlanRequest(BaseModel):
    plan_md: str


class ApproveRequest(BaseModel):
    feedback: Optional[str] = None


class RollbackRequest(BaseModel):
    checkpoint_id: str


class ProjectResponse(BaseModel):
    id: str
    name: str
    status: str
    plan_md: str | None
    stack_config_json: str | None
    container_id: str | None
    port: int | None
    created_at: str
    updated_at: str


# ── Endpoints ───────────────────────────────────────────────────────────


@router.post("/projects", response_model=ProjectResponse)
async def api_create_project(req: CreateProjectRequest) -> Any:
    """Create a new project."""
    project_id = str(uuid.uuid4())
    project = await create_project(project_id, req.name, req.description)
    return project


@router.get("/projects", response_model=list[ProjectResponse])
async def api_list_projects() -> Any:
    """List all projects."""
    return await get_all_projects()


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def api_get_project(project_id: str) -> Any:
    """Get project details."""
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/projects/{project_id}")
async def api_delete_project(project_id: str) -> dict[str, str]:
    """Delete a project (soft — stops execution, removes record)."""
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await runner_stop(project_id)
    # For MVP: just mark as deleted status instead of hard delete
    from orchestrator.models.project import update_project_status
    await update_project_status(project_id, "deleted")
    return {"status": "deleted", "project_id": project_id}


@router.put("/projects/{project_id}/plan")
async def api_update_plan(project_id: str, req: UpdatePlanRequest) -> dict[str, str]:
    """Manually update PLAN.md content."""
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await update_project_plan(project_id, req.plan_md)
    return {"status": "updated"}


@router.post("/projects/{project_id}/start")
async def api_start_project(project_id: str) -> dict[str, str]:
    """Start the Architect flow for a project.

    Launches the LangGraph graph as an async background task.
    """
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    result = await runner_start(project_id)
    return result


@router.post("/projects/{project_id}/approve")
async def api_approve_plan(project_id: str, req: ApproveRequest | None = None) -> dict[str, str]:
    """Approve PLAN.md (or any human intervention) and resume the graph."""
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    feedback = req.feedback if req else None
    result = await runner_resume(project_id, feedback)
    return result


@router.post("/projects/{project_id}/stop")
async def api_stop_project(project_id: str) -> dict[str, str]:
    """Stop (cancel) the active graph run for a project."""
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    result = await runner_stop(project_id)
    return result


@router.get("/projects/{project_id}/plan")
async def api_get_plan(project_id: str) -> dict[str, str | None]:
    """Get raw PLAN.md content."""
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"plan_md": project.get("plan_md")}


@router.get("/projects/{project_id}/history")
async def api_get_history(project_id: str) -> dict[str, Any]:
    """Get LangGraph checkpoint history for time-travel."""
    checkpoints = await get_checkpoints(project_id)
    return {"project_id": project_id, "checkpoints": checkpoints}


@router.post("/projects/{project_id}/rollback")
async def api_rollback(project_id: str, req: RollbackRequest) -> dict[str, str]:
    """Rollback project to a specific checkpoint via LangGraph state replay."""
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from orchestrator.graph.runner import _get_graph, _make_thread_config, is_running

    if is_running(project_id):
        raise HTTPException(
            status_code=409,
            detail="Cannot rollback while project is running. Stop it first.",
        )

    graph = _get_graph()
    config = _make_thread_config(project_id)
    target_checkpoint_id = req.checkpoint_id

    # Find the target checkpoint in history
    target_state = None
    async for checkpoint in graph.aget_state_history(config):
        cid = checkpoint.config.get("configurable", {}).get("checkpoint_id", "")
        if cid == target_checkpoint_id:
            target_state = checkpoint
            break

    if target_state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Checkpoint '{target_checkpoint_id}' not found for this project",
        )

    # Restore state by updating with the checkpoint's values
    checkpoint_config = {
        "configurable": {
            "thread_id": config["configurable"]["thread_id"],
            "checkpoint_id": target_checkpoint_id,
        }
    }
    await graph.aupdate_state(checkpoint_config, target_state.values)

    # Sync plan_md back to DB if present
    plan_md = target_state.values.get("plan_md", "")
    if plan_md:
        await update_project_plan(project_id, plan_md)

    phase = target_state.values.get("phase", "")
    await update_project_status(project_id, phase.lower() if phase else "paused")

    return {
        "status": "rolled_back",
        "checkpoint_id": target_checkpoint_id,
        "phase": phase,
    }



@router.get("/projects/{project_id}/logs")
async def api_get_logs(project_id: str) -> dict[str, Any]:
    """Get build logs for a project."""
    sessions = await get_sessions(project_id)
    # Collect task logs from all sessions
    import aiosqlite
    from orchestrator.models.project import _db_path
    all_logs: list[dict] = []
    if _db_path:
        async with aiosqlite.connect(_db_path) as db:
            db.row_factory = aiosqlite.Row
            for session in sessions:
                cursor = await db.execute(
                    "SELECT * FROM task_logs WHERE session_id = ? ORDER BY created_at",
                    (session["id"],),
                )
                rows = await cursor.fetchall()
                all_logs.extend(dict(row) for row in rows)
    return {"project_id": project_id, "logs": all_logs}


@router.get("/projects/{project_id}/sessions")
async def api_get_sessions(project_id: str) -> list[dict[str, Any]]:
    """Get execution sessions for a project."""
    return await get_sessions(project_id)


@router.get("/projects/{project_id}/chat-history")
async def api_get_chat_history(project_id: str) -> list[dict[str, Any]]:
    """Get chat messages for a project."""
    return await get_chat_messages(project_id)


@router.get("/projects/{project_id}/preview-url")
async def api_get_preview_url(project_id: str) -> dict[str, str | None]:
    """Get live preview URL for a project."""
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    port = project.get("port")
    url = f"http://localhost:{port}" if port else None
    return {"preview_url": url}
