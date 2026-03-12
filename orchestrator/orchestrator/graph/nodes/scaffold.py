"""Scaffold, approval, and preview nodes for the Automatron graph."""

from __future__ import annotations

import logging
import shlex
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage
from langgraph.types import interrupt

from orchestrator.config import settings
from orchestrator.docker_engine.manager import ContainerManager
from orchestrator.docker_engine.port_allocator import PortAllocator
from orchestrator.graph.state import AutomatronState
from orchestrator.llm.configuration import (
    builder_auth_provider,
    default_llm_config,
    normalize_llm_config,
    provider_api_key,
)
from orchestrator.plan_parser.parser import get_next_task, get_progress
from orchestrator.repository.manager import RepositoryManager

logger = logging.getLogger(__name__)

container_manager = ContainerManager()
port_allocator = PortAllocator(start=settings.port_range_start, end=settings.port_range_end)
repository_manager = RepositoryManager()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def plan_review_node(state: AutomatronState) -> dict:
    """Pause after plan generation or freeze escalation."""
    if state.get("container_id") and not state.get("requires_human", False):
        return {
            "requires_human": False,
            "human_intervention_reason": "",
            "project_stage": "building",
            "status": "building",
        }

    project_id = state["project_id"]
    reason = state.get("human_intervention_reason") or "Review and approve the technical plan."
    approval = interrupt(
        {
            "type": "plan_review",
            "project_id": project_id,
            "plan_md": state.get("plan_md", ""),
            "reason": reason,
        }
    )

    feedback = _extract_feedback(approval)
    result: dict = {
        "requires_human": False,
        "human_intervention_reason": "",
        "status": "planning",
    }

    if state.get("container_id"):
        result["project_stage"] = "planning"
    else:
        result["plan_approved"] = True
        result["plan_approved_at"] = _now()
        result["project_stage"] = "repo_preparing"

    if feedback:
        result["messages"] = [HumanMessage(content=f"[Human Feedback] {feedback}")]

    return result


async def repo_prepare_node(state: AutomatronState) -> dict:
    """Create the remote repository and reserve branch names."""
    metadata = await repository_manager.create_remote_repository(
        state["project_id"],
        state["project_name"],
    )
    return {
        "repo_name": metadata.repo_name,
        "repo_url": metadata.repo_url,
        "repo_clone_url": metadata.repo_clone_url,
        "default_branch": metadata.default_branch,
        "develop_branch": metadata.develop_branch,
        "feature_branch": metadata.feature_branch,
        "project_stage": "repo_preparing",
        "status": "planning",
    }


async def scaffold_node(state: AutomatronState) -> dict:
    """Create the sandbox container and bootstrap the local git workspace."""
    project_id = state["project_id"]
    stack_config = state.get("stack_config", {})
    port = await port_allocator.allocate(project_id)

    container_info = await container_manager.create_project_container(
        project_id=project_id,
        stack_config=stack_config,
        port=port,
    )

    init_script = stack_config.get("init_script") or "init-generic.sh"
    llm_config = normalize_llm_config(state.get("llm_config") or default_llm_config())
    builder_provider = llm_config["builder"]["provider"]
    builder_model = llm_config["builder"]["model"]
    script_path = f"/opt/automatron/scripts/{init_script}"
    try:
        await container_manager.exec_in_container(
            container_info.container_id,
            f"bash {script_path}",
            timeout=180,
        )
    except Exception as exc:
        logger.warning("Init script %s failed: %s", init_script, exc)

    provider_key = provider_api_key(builder_provider)
    if provider_key:
        try:
            await container_manager.exec_in_container(
                container_info.container_id,
                " ".join(
                    [
                        "cline auth",
                        f"-p {builder_auth_provider(builder_provider)}",
                        f"-k {shlex.quote(provider_key)}",
                        f"-m {shlex.quote(builder_model)}",
                    ]
                ),
                timeout=30,
            )
        except Exception as exc:
            logger.warning("Cline auth setup failed: %s", exc)

    repository_manager.ensure_deploy_supporting_docs(project_id, state["project_name"])
    repository_manager.initialize_workspace_repository(
        project_id,
        state["project_name"],
        repository_manager_metadata_from_state(state),
    )
    await repository_manager.ensure_remote_cicd(repository_manager_metadata_from_state(state))

    return {
        "container_id": container_info.container_id,
        "container_port": port,
        "repo_ready": True,
        "project_stage": "building",
        "status": "building",
    }


async def task_selector_node(state: AutomatronState) -> dict:
    plan_md = state.get("plan_md", "")
    progress = get_progress(plan_md)
    next_task = get_next_task(plan_md)

    if next_task is None:
        return {
            "current_task_index": -1,
            "current_task_text": "",
            "total_tasks": progress.total,
            "completed_tasks": progress.completed,
            "escalation_count": 0,
            "project_stage": "building",
            "status": "building",
        }

    previous_index = state.get("current_task_index", -1)
    escalation_count = 0 if next_task.index != previous_index else state.get("escalation_count", 0)

    return {
        "current_task_index": next_task.index,
        "current_task_text": f"{next_task.title}\n{next_task.description}".strip(),
        "total_tasks": progress.total,
        "completed_tasks": progress.completed,
        "escalation_count": escalation_count,
        "builder_status": "",
        "builder_output": "",
        "builder_error_detail": "",
        "project_stage": "building",
        "status": "building",
    }


async def freeze_node(state: AutomatronState) -> dict:
    task_index = state.get("current_task_index", -1)
    task_text = state.get("current_task_text", "")
    escalation_count = state.get("escalation_count", 0)
    reason = (
        f"Task #{task_index + 1} failed {escalation_count + 1} times.\n"
        f"Task: {task_text[:200]}\n"
        f"Last error: {state.get('builder_error_detail', '')[:500]}"
    )

    history = list(state.get("escalation_history", []))
    history.append(
        {
            "task_index": task_index,
            "status": "FROZEN",
            "timestamp": _now(),
            "reason": reason,
        }
    )
    return {
        "project_stage": "frozen",
        "status": "frozen",
        "requires_human": True,
        "human_intervention_reason": reason,
        "escalation_history": history,
    }


async def preview_check_node(state: AutomatronState) -> dict:
    project_id = state["project_id"]
    missing_artifacts = repository_manager.validate_deploy_artifacts(project_id)
    if missing_artifacts:
        raise RuntimeError(f"Missing deploy artifacts: {', '.join(missing_artifacts)}")

    repository_manager.commit_workspace_changes(
        project_id,
        "chore: finalize preview-ready workspace",
        branch=state.get("feature_branch") or None,
    )

    internal_port = int(state.get("stack_config", {}).get("port", 3000) or 3000)
    await container_manager.start_preview_process(
        state["container_id"],
        internal_port=internal_port,
        external_port=state["container_port"],
        stack_config=state.get("stack_config", {}),
        workspace_path=repository_manager.workspace_path(project_id),
    )
    await container_manager.wait_for_preview(state["container_id"], internal_port=internal_port)

    preview_url = f"http://localhost:{state['container_port']}"
    return {
        "preview_url": preview_url,
        "preview_status": "healthy",
        "preview_metadata": {"internal_port": internal_port, "checked_at": _now()},
        "project_stage": "awaiting_preview_approval",
        "status": "preview",
        "requires_human": True,
        "human_intervention_reason": "Review the live preview before promotion to develop.",
    }


async def preview_review_node(state: AutomatronState) -> dict:
    approval = interrupt(
        {
            "type": "preview_review",
            "project_id": state["project_id"],
            "preview_url": state.get("preview_url"),
            "reason": state.get("human_intervention_reason", "Review preview"),
        }
    )
    feedback = _extract_feedback(approval)
    result: dict = {
        "preview_approved": True,
        "preview_approved_at": _now(),
        "requires_human": False,
        "human_intervention_reason": "",
        "project_stage": "ready_for_deploy",
        "status": "ready_for_deploy",
    }
    if feedback:
        result["messages"] = [HumanMessage(content=f"[Preview Feedback] {feedback}")]
    return result


async def ready_for_deploy_node(state: AutomatronState) -> dict:
    repository_manager.merge_branch(
        state["project_id"],
        state["feature_branch"],
        state["develop_branch"],
        "chore: promote approved preview to develop",
    )
    return {
        "project_stage": "ready_for_deploy",
        "status": "ready_for_deploy",
        "requires_human": False,
    }


def _extract_feedback(value: object) -> str | None:
    if isinstance(value, dict):
        feedback = value.get("feedback")
        return str(feedback).strip() if feedback else None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def repository_manager_metadata_from_state(state: AutomatronState):
    from orchestrator.repository.manager import RepoMetadata

    return RepoMetadata(
        repo_name=state["repo_name"],
        repo_url=state["repo_url"],
        repo_clone_url=state["repo_clone_url"],
        default_branch=state.get("default_branch", "main"),
        develop_branch=state.get("develop_branch", "develop"),
        feature_branch=state.get("feature_branch", "feature/1-project"),
    )
