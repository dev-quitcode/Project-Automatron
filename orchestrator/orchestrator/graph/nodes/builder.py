"""Builder node — executes tasks via Cline CLI inside Docker containers."""

from __future__ import annotations

import logging
import shlex
import tempfile

from orchestrator.config import settings
from orchestrator.docker_engine.manager import ContainerManager
from orchestrator.graph.state import AutomatronState
from orchestrator.plan_parser.parser import get_global_rules

logger = logging.getLogger(__name__)

container_manager = ContainerManager()


async def builder_node(state: AutomatronState) -> dict:
    """Builder node: runs Cline CLI inside the project's Docker container.

    Sequence:
    1. Read current task + global rules from PLAN.md frontmatter
    2. Build Cline prompt with task + context + rules
    3. Write prompt to a temp file inside the container (avoids shell injection)
    4. Execute `cline -y --task-file` inside Docker container
    5. Capture stdout/stderr
    6. Read updated PLAN.md from container (Cline may mark [x])
    7. Return output for status classification
    """
    container_id = state.get("container_id", "")
    task_text = state.get("current_task_text", "")
    task_index = state.get("current_task_index", -1)
    plan_md = state.get("plan_md", "")

    if not container_id:
        logger.error("Builder: no container_id in state")
        return {
            "builder_status": "BLOCKER",
            "builder_output": "",
            "builder_error_detail": "No Docker container available",
            "phase": "EXECUTING",
        }

    if not task_text:
        logger.error("Builder: no task_text in state")
        return {
            "builder_status": "BLOCKER",
            "builder_output": "",
            "builder_error_detail": "No task text provided",
            "phase": "EXECUTING",
        }

    # Extract global rules from PLAN.md frontmatter
    global_rules = get_global_rules(plan_md)
    rules_text = "\n".join(f"- {r}" for r in global_rules) if global_rules else "None"

    # Build the Cline prompt
    cline_prompt = (
        f"You are a coder. Execute ONLY this task:\n\n"
        f"TASK: {task_text}\n\n"
        f"GLOBAL RULES:\n{rules_text}\n\n"
        f"IMPORTANT:\n"
        f"- Do NOT change the architecture\n"
        f"- Do NOT delete existing files unless explicitly instructed\n"
        f"- Follow the global rules strictly\n"
        f"- Work in /workspace directory\n"
    )

    logger.info(
        "Builder: executing task %d in container %s",
        task_index,
        container_id[:12],
    )

    # Copy PLAN.md into container
    try:
        await container_manager.copy_file_to_container(
            container_id, plan_md, "/workspace/PLAN.md"
        )
    except Exception as e:
        logger.warning("Builder: failed to copy PLAN.md: %s", e)

    # Write prompt to a temp file inside the container to avoid shell injection.
    # The prompt may contain quotes, backticks, etc. — file-based approach is safe.
    prompt_container_path = "/tmp/automatron_task_prompt.txt"
    try:
        await container_manager.copy_file_to_container(
            container_id, cline_prompt, prompt_container_path
        )
    except Exception as e:
        logger.error("Builder: failed to write prompt file: %s", e)
        return {
            "builder_status": "BLOCKER",
            "builder_output": str(e),
            "builder_error_detail": f"Failed to write prompt file: {e}",
            "phase": "EXECUTING",
        }

    # Execute Cline CLI using the prompt file — avoids shell injection
    # shlex.quote is used for the model name and file path as extra safety
    model = shlex.quote(settings.builder_model)
    timeout = settings.builder_cline_timeout
    prompt_path_quoted = shlex.quote(prompt_container_path)

    cline_command = (
        f"cline -y -m {model} --timeout {timeout} "
        f"--cwd /workspace --task-file {prompt_path_quoted}"
    )

    try:
        result = await container_manager.exec_in_container(
            container_id, cline_command, timeout=timeout + 30
        )
        exit_code = result.exit_code
        output = result.output
    except Exception as e:
        logger.error("Builder: Cline execution failed: %s", e)
        return {
            "builder_status": "BLOCKER",
            "builder_output": str(e),
            "builder_error_detail": f"Cline CLI execution error: {e}",
            "phase": "EXECUTING",
        }

    # Try to read updated PLAN.md from container
    updated_plan = plan_md
    try:
        updated_plan = await container_manager.read_file_from_container(
            container_id, "/workspace/PLAN.md"
        )
    except Exception as e:
        logger.warning("Builder: could not read PLAN.md from container: %s", e)

    logger.info(
        "Builder: task %d completed (exit_code=%d, output=%d chars)",
        task_index,
        exit_code,
        len(output),
    )

    return {
        "builder_output": output,
        "builder_error_detail": "" if exit_code == 0 else output[-2000:],
        "plan_md": updated_plan,
        "phase": "EXECUTING",
        # builder_status will be set by status_classifier_node
    }
