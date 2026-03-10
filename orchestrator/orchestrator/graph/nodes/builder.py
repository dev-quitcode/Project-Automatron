"""Builder node — executes tasks via Cline CLI inside Docker containers."""

from __future__ import annotations

import logging
import shlex
import time

from orchestrator.config import settings
from orchestrator.docker_engine.manager import ContainerManager
from orchestrator.graph.state import AutomatronState
from orchestrator.plan_parser.parser import get_global_rules

logger = logging.getLogger(__name__)

container_manager = ContainerManager()


async def builder_node(state: AutomatronState) -> dict:
    """Run the current task in the project container."""
    container_id = state.get("container_id", "")
    task_text = state.get("current_task_text", "")
    task_index = state.get("current_task_index", -1)
    plan_md = state.get("plan_md", "")

    if not container_id:
        return {
            "builder_status": "BLOCKER",
            "builder_error_detail": "No Docker container available",
            "builder_output": "",
            "project_stage": "building",
            "status": "building",
        }
    if not task_text:
        return {
            "builder_status": "BLOCKER",
            "builder_error_detail": "No task text provided",
            "builder_output": "",
            "project_stage": "building",
            "status": "building",
        }

    global_rules = get_global_rules(plan_md)
    rules_text = "\n".join(f"- {rule}" for rule in global_rules) if global_rules else "- None"
    stack_config = state.get("stack_config", {})
    preview_port = state.get("container_port", 3000)
    preview_requirement = (
        "By the end of the plan, the repo must contain Dockerfile, .env.example, "
        "deploy/docker-compose.yml, DEPLOY.md, .github/workflows/ci.yml, "
        "and .github/workflows/deploy.yml. Preview must be able to run on the allocated port."
    )

    cline_prompt = (
        "You are Automatron Builder operating inside the project workspace.\n\n"
        f"CURRENT TASK:\n{task_text}\n\n"
        f"STACK CONFIG:\n{stack_config}\n\n"
        f"GLOBAL RULES:\n{rules_text}\n\n"
        "REQUIRED OUTPUT CONTRACT:\n"
        f"- {preview_requirement}\n"
        f"- The active preview port is {preview_port}\n"
        "- Keep PLAN.md in sync with completed tasks\n"
        "- Do not remove the existing git repository\n"
        "- Preserve the generated GitHub Actions workflows unless intentionally updating them\n"
        "- Do not access external deployment credentials\n"
    )

    try:
        await container_manager.copy_file_to_container(container_id, plan_md, "/workspace/PLAN.md")
        await container_manager.copy_file_to_container(
            container_id,
            cline_prompt,
            "/tmp/automatron_task_prompt.txt",
        )
    except Exception as exc:
        return {
            "builder_status": "BLOCKER",
            "builder_output": str(exc),
            "builder_error_detail": f"Failed to prepare Cline prompt: {exc}",
            "project_stage": "building",
            "status": "building",
        }

    model = shlex.quote(settings.builder_model)
    timeout = settings.builder_cline_timeout
    command = (
        f"cline -y -m {model} --timeout {timeout} "
        "--cwd /workspace --task-file /tmp/automatron_task_prompt.txt"
    )

    started = time.monotonic()
    try:
        result = await container_manager.exec_in_container(container_id, command, timeout=timeout + 30)
        output = result.output
        exit_code = result.exit_code
    except Exception as exc:
        return {
            "builder_status": "BLOCKER",
            "builder_output": str(exc),
            "builder_error_detail": f"Cline execution failed: {exc}",
            "builder_duration_s": time.monotonic() - started,
            "project_stage": "building",
            "status": "building",
        }

    updated_plan = plan_md
    try:
        updated_plan = await container_manager.read_file_from_container(container_id, "/workspace/PLAN.md")
    except Exception as exc:
        logger.warning("Could not read PLAN.md after task %d: %s", task_index, exc)

    return {
        "builder_output": output,
        "builder_error_detail": "" if exit_code == 0 else output[-2000:],
        "builder_exit_code": exit_code,
        "builder_duration_s": time.monotonic() - started,
        "plan_md": updated_plan,
        "project_stage": "building",
        "status": "building",
    }
