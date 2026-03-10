"""Graph runner — manages LangGraph execution sessions and deploys."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from orchestrator.api.websocket import (
    emit_human_required,
    emit_plan_updated,
    emit_status_update,
)
from orchestrator.config import settings
from orchestrator.deployment.manager import DeploymentManager
from orchestrator.graph.graph import compile_graph
from orchestrator.models.project import (
    get_project,
    record_approval,
    sync_project_from_state,
    update_project_cicd,
    update_project_deploy_status,
    update_project_stage,
    update_project_status,
    upsert_deploy_run,
)
from orchestrator.models.session import create_session, end_session
from orchestrator.repository.manager import RepositoryManager

logger = logging.getLogger(__name__)

_active_runs: dict[str, asyncio.Task] = {}
_compiled_graph = None
repository_manager = RepositoryManager()
# Retained for manual fallback deploy mode outside the primary GitHub Actions path.
manual_deployment_manager = DeploymentManager()


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = compile_graph()
    return _compiled_graph


def _make_thread_config(project_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": f"automatron:{project_id}"}}


def _is_interrupt_result(result: Any) -> bool:
    return isinstance(result, dict) and "__interrupt__" in result


def _status_from_stage(stage: str) -> str:
    mapping = {
        "intake": "pending",
        "planning": "planning",
        "awaiting_plan_approval": "planning",
        "repo_preparing": "planning",
        "scaffolding": "building",
        "building": "building",
        "awaiting_preview_approval": "preview",
        "ready_for_deploy": "ready_for_deploy",
        "deploying": "deploying",
        "deployed": "deployed",
        "frozen": "frozen",
        "error": "error",
    }
    return mapping.get(stage, "pending")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def sync_cicd_status(project_id: str) -> dict[str, str]:
    project = await get_project(project_id)
    if not project:
        return {"status": "not_found", "project_id": project_id}
    if not project.get("repo_name"):
        return {"status": "not_configured", "project_id": project_id}

    try:
        result = await repository_manager.sync_remote_cicd_status(
            project["repo_name"],
            feature_branch=project.get("feature_branch") or "",
            develop_branch=project.get("develop_branch") or "develop",
            default_branch=project.get("default_branch") or "main",
        )
    except Exception:
        logger.exception("Failed to sync CI/CD status for %s", project_id)
        return {"status": "failed", "project_id": project_id}

    ci = result["ci"]
    deploy = result["deploy"]
    ci_status = ci.status if ci.run_id else project.get("ci_status") or "not_configured"
    deploy_status = deploy.status if deploy.run_id else project.get("deploy_status") or "not_configured"

    await update_project_cicd(
        project_id,
        ci_status=ci_status,
        ci_run_id=ci.run_id if ci.run_id else project.get("ci_run_id"),
        ci_run_url=ci.run_url if ci.run_url else project.get("ci_run_url"),
        deploy_status=deploy_status,
        deploy_run_url=deploy.run_url if deploy.run_url else project.get("deploy_run_url"),
        deploy_commit_sha=deploy.head_sha if deploy.head_sha else project.get("deploy_commit_sha"),
        github_environment_name=project.get("github_environment_name") or settings.github_environment_name,
        last_workflow_sync_at=_now(),
    )

    if deploy.run_id:
        deploy_summary = {
            "provider": "github_actions",
            "run_url": deploy.run_url,
            "commit_sha": deploy.head_sha,
        }
        await upsert_deploy_run(
            f"github-{deploy.run_id}",
            project_id,
            deploy.status,
            project.get("default_branch") or "main",
            f"GitHub Actions {deploy.status}",
            summary=deploy_summary,
            deployed_at=deploy.updated_at if deploy.status == "deployed" else None,
        )

    if deploy_status == "deployed":
        await update_project_stage(project_id, "deployed")
        await update_project_status(project_id, "deployed")
        await update_project_deploy_status(
            project_id,
            "deployed",
            last_deploy_at=deploy.updated_at or _now(),
            last_deploy_run_id=deploy.run_id,
            deploy_run_url=deploy.run_url,
            deploy_commit_sha=deploy.head_sha,
        )
        await emit_status_update(project_id, status="deployed", stage="deployed", progress={})
    elif deploy_status in {"queued", "running"}:
        await update_project_stage(project_id, "deploying")
        await update_project_status(project_id, "deploying")
        await update_project_deploy_status(
            project_id,
            deploy_status,
            last_deploy_run_id=deploy.run_id,
            deploy_run_url=deploy.run_url,
            deploy_commit_sha=deploy.head_sha,
        )
        await emit_status_update(project_id, status="deploying", stage="deploying", progress={})
    elif deploy_status == "failed":
        await update_project_stage(project_id, "error")
        await update_project_status(project_id, "error")
        await update_project_deploy_status(
            project_id,
            "failed",
            last_deploy_run_id=deploy.run_id,
            deploy_run_url=deploy.run_url,
            deploy_commit_sha=deploy.head_sha,
        )
        await emit_status_update(project_id, status="error", stage="error", progress={})

    return {
        "status": "synced",
        "project_id": project_id,
        "ci_status": ci_status,
        "deploy_status": deploy_status,
    }


async def _persist_and_emit(project_id: str, graph: Any, config: dict[str, Any]) -> dict[str, Any]:
    snapshot = await graph.aget_state(config)
    values = snapshot.values if snapshot and snapshot.values else {}
    if values:
        if "status" not in values and values.get("project_stage"):
            values["status"] = _status_from_stage(values["project_stage"])
        await sync_project_from_state(project_id, values)
        await emit_status_update(
            project_id,
            status=values.get("status", "pending"),
            stage=values.get("project_stage", "intake"),
            progress={
                "total": values.get("total_tasks", 0),
                "completed": values.get("completed_tasks", 0),
            },
            preview_url=values.get("preview_url"),
        )
        if values.get("plan_md"):
            await emit_plan_updated(project_id, values["plan_md"])
        if values.get("requires_human"):
            await emit_human_required(
                project_id,
                values.get("human_intervention_reason", "Review required"),
                stage=values.get("project_stage"),
            )
    return values


async def _run_graph(
    project_id: str,
    *,
    initial_state: dict[str, Any] | None = None,
    resume_payload: dict[str, Any] | None = None,
) -> None:
    graph = _get_graph()
    config = _make_thread_config(project_id)
    session_id = str(uuid.uuid4())

    try:
        phase = "PLANNING" if initial_state else "RESUME"
        await create_session(session_id, project_id, config["configurable"]["thread_id"], phase)

        if initial_state is not None:
            initial_state["session_id"] = session_id
            await graph.ainvoke(initial_state, config)
        else:
            await graph.aupdate_state(config, {"session_id": session_id})
            await graph.ainvoke(Command(resume=resume_payload or {"approved": True}), config)

        values = await _persist_and_emit(project_id, graph, config)
        stage = values.get("project_stage", "pending")
        if stage == "ready_for_deploy":
            await update_project_stage(project_id, "ready_for_deploy")
            await update_project_status(project_id, "ready_for_deploy")
        elif values.get("requires_human"):
            await update_project_status(project_id, _status_from_stage(stage))
        elif stage == "frozen":
            await update_project_status(project_id, "frozen")

    except asyncio.CancelledError:
        logger.info("Graph run cancelled for %s", project_id)
        await update_project_status(project_id, "paused")
        await emit_status_update(project_id, status="paused", stage="intake", progress={})
    except Exception:
        logger.exception("Graph run failed for %s", project_id)
        await update_project_stage(project_id, "error")
        await update_project_status(project_id, "error")
        await emit_status_update(project_id, status="error", stage="error", progress={})
    finally:
        await end_session(session_id)
        _active_runs.pop(project_id, None)


async def start_project(project_id: str) -> dict[str, str]:
    if project_id in _active_runs:
        return {"status": "already_running", "project_id": project_id}

    project = await get_project(project_id)
    if not project:
        return {"status": "not_found", "project_id": project_id}

    initial_state: dict[str, Any] = {
        "project_id": project_id,
        "project_name": project["name"],
        "intake_text": project.get("intake_text", ""),
        "intake_source": project.get("intake_source", "manual"),
        "source_ref": project.get("source_ref") or "",
        "plan_md": project.get("plan_md", ""),
        "stack_config": project.get("stack_config", {}),
        "current_task_index": 0,
        "current_task_text": "",
        "total_tasks": 0,
        "completed_tasks": 0,
        "messages": [HumanMessage(content=project.get("intake_text", ""))],
        "builder_status": "",
        "builder_output": "",
        "builder_error_detail": "",
        "escalation_count": 0,
        "escalation_history": [],
        "container_id": project.get("container_id") or "",
        "container_port": project.get("port") or 0,
        "repo_name": project.get("repo_name") or "",
        "repo_url": project.get("repo_url") or "",
        "repo_clone_url": project.get("repo_clone_url") or "",
        "default_branch": project.get("default_branch") or "main",
        "develop_branch": project.get("develop_branch") or "develop",
        "feature_branch": project.get("feature_branch") or repository_manager.create_feature_branch_name(project["name"]),
        "repo_ready": bool(project.get("repo_ready", False)),
        "preview_url": project.get("preview_url") or "",
        "preview_status": project.get("preview_status") or "pending",
        "preview_metadata": project.get("preview_metadata", {}),
        "deploy_target": project.get("deploy_target", {}),
        "project_stage": "planning",
        "status": "planning",
        "requires_human": False,
        "human_intervention_reason": "",
        "plan_approved": bool(project.get("plan_approved", False)),
        "preview_approved": bool(project.get("preview_approved", False)),
    }

    await update_project_stage(project_id, "planning")
    await update_project_status(project_id, "planning")
    task = asyncio.create_task(_run_graph(project_id, initial_state=initial_state))
    _active_runs[project_id] = task
    return {"status": "started", "project_id": project_id}


async def resume_project(
    project_id: str,
    *,
    approval_type: str,
    feedback: str | None = None,
) -> dict[str, str]:
    if project_id in _active_runs:
        return {"status": "already_running", "project_id": project_id}

    project = await get_project(project_id)
    if not project:
        return {"status": "not_found", "project_id": project_id}

    await record_approval(project_id, approval_type, True, feedback=feedback)
    payload = {"approved": True, "feedback": feedback, "approval_type": approval_type}
    task = asyncio.create_task(_run_graph(project_id, resume_payload=payload))
    _active_runs[project_id] = task
    return {"status": "resumed", "project_id": project_id, "approval_type": approval_type}


async def deploy_project(project_id: str) -> dict[str, str]:
    project = await get_project(project_id)
    if not project:
        return {"status": "not_found", "project_id": project_id}
    if project.get("project_stage") != "ready_for_deploy":
        return {"status": "invalid_stage", "project_id": project_id}
    if not project.get("deploy_target"):
        return {"status": "missing_deploy_target", "project_id": project_id}
    if not project.get("repo_name"):
        return {"status": "missing_repository", "project_id": project_id}

    await update_project_stage(project_id, "deploying")
    await update_project_status(project_id, "deploying")
    await update_project_deploy_status(project_id, "queued")
    await update_project_cicd(
        project_id,
        deploy_status="queued",
        github_environment_name=project.get("github_environment_name") or settings.github_environment_name,
        last_workflow_sync_at=_now(),
    )
    await emit_status_update(project_id, status="deploying", stage="deploying", progress={})

    try:
        deploy_sha = repository_manager.merge_branch(
            project_id,
            project.get("develop_branch") or "develop",
            project.get("default_branch") or "main",
            "chore: promote develop to main for deploy",
        )
        await update_project_deploy_status(
            project_id,
            "queued",
            deploy_commit_sha=deploy_sha,
        )
        await update_project_cicd(project_id, deploy_commit_sha=deploy_sha, deploy_status="queued")
        await asyncio.sleep(2)
        sync_result = await sync_cicd_status(project_id)
        return {
            "status": sync_result.get("deploy_status", "queued"),
            "project_id": project_id,
        }
    except Exception as exc:
        logger.exception("Deploy failed for %s", project_id)
        await update_project_stage(project_id, "error")
        await update_project_status(project_id, "error")
        await update_project_deploy_status(project_id, "failed")
        await emit_status_update(project_id, status="error", stage="error", progress={})
        return {"status": "failed", "project_id": project_id}


async def stop_project(project_id: str) -> dict[str, str]:
    task = _active_runs.pop(project_id, None)
    if task:
        task.cancel()
        await update_project_status(project_id, "paused")
        return {"status": "stopped", "project_id": project_id}
    return {"status": "not_running", "project_id": project_id}


def is_running(project_id: str) -> bool:
    return project_id in _active_runs


async def get_checkpoints(project_id: str) -> list[dict[str, Any]]:
    graph = _get_graph()
    config = _make_thread_config(project_id)

    checkpoints: list[dict[str, Any]] = []
    try:
        async for checkpoint in graph.aget_state_history(config):
            checkpoints.append(
                {
                    "config": checkpoint.config,
                    "created_at": checkpoint.created_at,
                    "parent_config": checkpoint.parent_config,
                    "values_summary": {
                        "project_stage": checkpoint.values.get("project_stage", ""),
                        "status": checkpoint.values.get("status", ""),
                        "current_task_index": checkpoint.values.get("current_task_index", 0),
                        "completed_tasks": checkpoint.values.get("completed_tasks", 0),
                        "total_tasks": checkpoint.values.get("total_tasks", 0),
                    },
                }
            )
    except Exception:
        logger.warning("Failed to load checkpoints for %s", project_id)
    return checkpoints
