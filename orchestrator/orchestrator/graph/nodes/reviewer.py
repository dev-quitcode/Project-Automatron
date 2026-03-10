"""Status classifier node — classifies builder output and persists task results."""

from __future__ import annotations

import json
import logging
import uuid

from langchain_core.messages import HumanMessage, SystemMessage

from orchestrator.api.websocket import emit_builder_log
from orchestrator.graph.state import AutomatronState
from orchestrator.llm.prompts import load_prompt
from orchestrator.llm.provider import call_llm
from orchestrator.models.project import save_task_log
from orchestrator.repository.manager import RepositoryManager

logger = logging.getLogger(__name__)

repository_manager = RepositoryManager()


async def status_classifier_node(state: AutomatronState) -> dict:
    builder_output = state.get("builder_output", "")
    builder_error = state.get("builder_error_detail", "")
    task_text = state.get("current_task_text", "")
    task_index = state.get("current_task_index", -1)
    session_id = state.get("session_id", "")

    if not builder_error and _looks_successful(builder_output):
        status = "SUCCESS"
        reason = ""
    else:
        system_prompt = load_prompt("reviewer", "v1")
        classification_input = (
            f"Task: {task_text}\n\n"
            f"Builder Output (last 3000 chars):\n```\n{builder_output[-3000:]}\n```\n\n"
            f"Error Details:\n{builder_error}\n\n"
            'Return JSON: {"status": "...", "reason": "..."}'
        )
        try:
            response = await call_llm(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=classification_input),
                ],
                model="gpt-4.1-mini",
            )
            result = _parse_classification(response)
            status = result["status"]
            reason = result.get("reason", "")
        except Exception as exc:
            logger.error("Reviewer classification failed: %s", exc)
            status = "AMBIGUITY"
            reason = f"Classification failed: {exc}"

    if status in ("SUCCESS", "SILENT_DECISION"):
        commit_message = f"builder: task {task_index + 1} {task_text.splitlines()[0][:72]}"
        try:
            repository_manager.commit_workspace_changes(
                state["project_id"],
                commit_message,
                branch=state.get("feature_branch") or None,
            )
        except Exception as exc:
            logger.warning("Failed to commit task %d changes: %s", task_index, exc)

    if session_id:
        await save_task_log(
            str(uuid.uuid4()),
            session_id,
            task_index,
            task_text,
            status,
            builder_output,
            float(state.get("builder_duration_s", 0.0)),
        )

    await emit_builder_log(
        state["project_id"],
        task_index=task_index,
        task_text=task_text,
        output=builder_output,
        status=status,
    )

    return {
        "builder_status": status,
        "builder_error_detail": reason,
        "project_stage": "building",
        "status": "building",
    }


def _looks_successful(output: str) -> bool:
    output_lower = output.lower()
    error_indicators = [
        "error:",
        "error!",
        "failed",
        "exception",
        "traceback",
        "fatal",
        "cannot find",
        "not found",
        "permission denied",
        "enoent",
        "eacces",
    ]
    return not any(indicator in output_lower for indicator in error_indicators)


def _parse_classification(response: str) -> dict[str, str]:
    try:
        if "```json" in response:
            start = response.index("```json") + len("```json")
            end = response.index("```", start)
            return json.loads(response[start:end].strip())
        if "```" in response:
            start = response.index("```") + 3
            end = response.index("```", start)
            return json.loads(response[start:end].strip())
        return json.loads(response.strip())
    except (ValueError, json.JSONDecodeError):
        pass

    response_upper = response.upper()
    for status in ("BLOCKER", "AMBIGUITY", "SILENT_DECISION", "SUCCESS"):
        if status in response_upper:
            return {"status": status, "reason": response[:200]}

    return {"status": "AMBIGUITY", "reason": "Could not parse classification"}
