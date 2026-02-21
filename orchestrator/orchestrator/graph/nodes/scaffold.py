"""Scaffold and utility nodes for the Automatron graph."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from langgraph.types import interrupt

from orchestrator.config import settings
from orchestrator.docker_engine.manager import ContainerManager
from orchestrator.docker_engine.port_allocator import PortAllocator
from orchestrator.graph.state import AutomatronState
from orchestrator.plan_parser.parser import get_next_task, get_progress

logger = logging.getLogger(__name__)

container_manager = ContainerManager()
port_allocator = PortAllocator(
    start=settings.port_range_start,
    end=settings.port_range_end,
)


async def human_review_node(state: AutomatronState) -> dict:
    """Human-in-the-loop node: pauses execution for human review of PLAN.md.

    Uses LangGraph's `interrupt()` to pause the graph. The graph resumes
    when the human calls the `/approve` endpoint (Command(resume=True)).
    """
    plan_md = state.get("plan_md", "")
    phase = state.get("phase", "PLANNING")

    logger.info("Human Review: waiting for approval (phase=%s)", phase)

    # interrupt() pauses execution and returns to the caller
    # On resume, the node re-executes from the beginning
    approved = interrupt({
        "type": "plan_review",
        "message": "Please review and approve PLAN.md",
        "plan_md": plan_md,
        "phase": phase,
    })

    logger.info("Human Review: approved=%s", approved)
    return {
        "phase": "SCAFFOLDING" if phase == "PLANNING" else "EXECUTING",
        "requires_human": False,
        "human_intervention_reason": "",
    }


async def scaffold_node(state: AutomatronState) -> dict:
    """Scaffold node: creates Docker container and initializes the project.

    1. Allocate a port
    2. Create Docker container from Golden Image
    3. Run scaffold/init script based on STACK_CONFIG
    4. Configure Cline CLI auth inside container
    """
    project_id = state["project_id"]
    stack_config = state.get("stack_config", {})

    logger.info("Scaffold: initializing container for project %s", project_id)

    # Allocate port
    port = await port_allocator.allocate(project_id)
    logger.info("Scaffold: allocated port %d for project %s", port, project_id)

    # Create container
    container_info = await container_manager.create_project_container(
        project_id=project_id,
        stack_config=stack_config,
        port=port,
    )

    # Run init script if available
    init_script = stack_config.get("init_script", "")
    if init_script:
        script_path = f"/opt/automatron/scripts/{init_script}"
        try:
            result = await container_manager.exec_in_container(
                container_info.container_id,
                f"bash {script_path}",
                timeout=120,
            )
            logger.info(
                "Scaffold: init script %s completed (exit=%d)",
                init_script,
                result.exit_code,
            )
        except Exception as e:
            logger.warning("Scaffold: init script failed: %s — Cline will handle init", e)
    else:
        logger.info("Scaffold: no init script — Cline will handle project init")

    # Configure Cline auth inside container
    try:
        cline_auth_cmd = (
            f"cline auth -p openai -k $OPENAI_API_KEY -m {settings.builder_model}"
        )
        await container_manager.exec_in_container(
            container_info.container_id, cline_auth_cmd, timeout=30
        )
        logger.info("Scaffold: Cline CLI configured in container")
    except Exception as e:
        logger.warning("Scaffold: Cline auth setup failed: %s", e)

    return {
        "container_id": container_info.container_id,
        "container_port": port,
        "phase": "EXECUTING",
    }


async def task_selector_node(state: AutomatronState) -> dict:
    """Task selector: finds the next uncompleted task in PLAN.md.

    Parses PLAN.md to find the first `- [ ]` checkbox.
    If no tasks remain, sets current_task_index to -1 (signals completion).
    """
    plan_md = state.get("plan_md", "")
    progress = get_progress(plan_md)

    next_task = get_next_task(plan_md)

    if next_task is None:
        logger.info("Task Selector: all tasks completed (%d/%d)", progress.completed, progress.total)
        return {
            "current_task_index": -1,
            "current_task_text": "",
            "total_tasks": progress.total,
            "completed_tasks": progress.completed,
            "escalation_count": 0,  # Reset for next cycle
        }

    logger.info(
        "Task Selector: selected task %d/%d: %s",
        next_task.index + 1,
        progress.total,
        next_task.title[:60],
    )

    # Reset escalation count when moving to a NEW task
    previous_index = state.get("current_task_index", -1)
    escalation_count = (
        0 if next_task.index != previous_index else state.get("escalation_count", 0)
    )

    return {
        "current_task_index": next_task.index,
        "current_task_text": f"{next_task.title}\n{next_task.description}",
        "total_tasks": progress.total,
        "completed_tasks": progress.completed,
        "escalation_count": escalation_count,
        "builder_status": "",  # Reset
        "builder_output": "",
        "builder_error_detail": "",
    }


async def freeze_node(state: AutomatronState) -> dict:
    """Freeze node: anti-loop protection.

    When a task fails too many times, freeze the system and request
    human intervention.
    """
    task_index = state.get("current_task_index", -1)
    task_text = state.get("current_task_text", "")
    escalation_count = state.get("escalation_count", 0)

    reason = (
        f"Anti-Loop Protection: Task #{task_index + 1} failed {escalation_count + 1} times.\n"
        f"Task: {task_text[:200]}\n"
        f"Last error: {state.get('builder_error_detail', '')[:500]}"
    )

    logger.error("FREEZE: %s", reason)

    # Record in escalation history
    history = list(state.get("escalation_history", []))
    history.append({
        "task_index": task_index,
        "status": "FROZEN",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
    })

    return {
        "phase": "FROZEN",
        "requires_human": True,
        "human_intervention_reason": reason,
        "escalation_history": history,
    }


async def completion_node(state: AutomatronState) -> dict:
    """Completion node: finalize the project.

    All tasks in PLAN.md are marked [x].
    """
    project_id = state["project_id"]
    completed = state.get("completed_tasks", 0)
    total = state.get("total_tasks", 0)

    logger.info(
        "COMPLETION: Project %s finished — %d/%d tasks completed",
        project_id,
        completed,
        total,
    )

    return {
        "phase": "COMPLETED",
        "requires_human": False,
    }
