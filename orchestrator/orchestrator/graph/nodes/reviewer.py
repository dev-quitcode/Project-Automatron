"""Status classifier node — classifies Cline output into 4 statuses."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import SystemMessage, HumanMessage

from orchestrator.graph.state import AutomatronState
from orchestrator.llm.prompts import load_prompt
from orchestrator.llm.provider import call_llm

logger = logging.getLogger(__name__)


async def status_classifier_node(state: AutomatronState) -> dict:
    """Classify the builder output into one of 4 statuses.

    Fast path: exit code 0 + no obvious errors → SUCCESS (skip LLM call)
    Full classification: exit code != 0 → LLM-based classification

    Returns:
        dict with builder_status and optionally builder_error_detail
    """
    builder_output = state.get("builder_output", "")
    builder_error = state.get("builder_error_detail", "")
    task_text = state.get("current_task_text", "")
    task_index = state.get("current_task_index", -1)

    # Fast path: no errors → SUCCESS
    if not builder_error and _looks_successful(builder_output):
        logger.info("Status Classifier: fast-path SUCCESS for task %d", task_index)
        return {
            "builder_status": "SUCCESS",
        }

    # Full LLM classification
    logger.info("Status Classifier: LLM classification for task %d", task_index)

    system_prompt = load_prompt("reviewer", "v1")
    classification_input = (
        f"Task: {task_text}\n\n"
        f"Builder Output (last 3000 chars):\n"
        f"```\n{builder_output[-3000:]}\n```\n\n"
        f"Error Details:\n{builder_error}\n\n"
        f"Classify this output into one of: SUCCESS, BLOCKER, AMBIGUITY, SILENT_DECISION\n"
        f"Respond with JSON: {{\"status\": \"...\", \"reason\": \"...\", \"suggestion\": \"...\"}}"
    )

    try:
        response = await call_llm(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=classification_input),
            ],
            model="gpt-4.1-mini",  # Lightweight model for classification
        )

        result = _parse_classification(response)
        logger.info(
            "Status Classifier: task %d → %s (reason: %s)",
            task_index,
            result["status"],
            result.get("reason", "")[:100],
        )
        return {
            "builder_status": result["status"],
            "builder_error_detail": result.get("reason", ""),
        }

    except Exception as e:
        logger.error("Status Classifier: LLM call failed: %s", e)
        # If classification fails, treat as AMBIGUITY (safe default)
        return {
            "builder_status": "AMBIGUITY",
            "builder_error_detail": f"Classification failed: {e}",
        }


def _looks_successful(output: str) -> bool:
    """Quick heuristic check if output looks successful."""
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


def _parse_classification(response: str) -> dict:
    """Parse JSON classification from LLM response."""
    # Try to extract JSON from response
    try:
        # Look for JSON in code block
        if "```json" in response:
            start = response.index("```json") + len("```json")
            end = response.index("```", start)
            return json.loads(response[start:end].strip())
        if "```" in response:
            start = response.index("```") + 3
            end = response.index("```", start)
            return json.loads(response[start:end].strip())
        # Try parsing entire response as JSON
        return json.loads(response.strip())
    except (ValueError, json.JSONDecodeError):
        pass

    # Fallback: look for status keywords in raw text
    response_upper = response.upper()
    for status in ("BLOCKER", "AMBIGUITY", "SILENT_DECISION", "SUCCESS"):
        if status in response_upper:
            return {"status": status, "reason": response[:200]}

    return {"status": "AMBIGUITY", "reason": "Could not parse classification"}
