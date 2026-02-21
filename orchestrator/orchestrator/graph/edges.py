"""Conditional edge functions for the Automatron graph."""

from __future__ import annotations

import logging
from typing import Literal

from orchestrator.graph.state import AutomatronState

logger = logging.getLogger(__name__)

# Maximum escalations per task before freezing
MAX_ESCALATIONS = 2


def route_after_task_selector(
    state: AutomatronState,
) -> Literal["builder", "completion"]:
    """Route after task_selector: if tasks remain → builder, else → completion."""
    if state["current_task_index"] < 0:
        logger.info("All tasks completed — routing to completion")
        return "completion"
    logger.info(
        "Task %d selected — routing to builder",
        state["current_task_index"],
    )
    return "builder"


def route_after_status_classifier(
    state: AutomatronState,
) -> Literal["task_selector", "freeze", "architect"]:
    """Route after status_classifier based on builder status.

    - SUCCESS / SILENT_DECISION → next task (task_selector)
    - BLOCKER / AMBIGUITY → check escalation count
      - if count > MAX_ESCALATIONS → freeze (anti-loop)
      - else → architect (re-plan)
    """
    status = state["builder_status"]

    if status in ("SUCCESS", "SILENT_DECISION"):
        logger.info("Builder status %s — moving to next task", status)
        return "task_selector"

    # BLOCKER or AMBIGUITY
    escalation_count = state.get("escalation_count", 0)
    logger.warning(
        "Builder status %s (escalation #%d for task %d)",
        status,
        escalation_count,
        state["current_task_index"],
    )

    if escalation_count >= MAX_ESCALATIONS:
        logger.error(
            "Anti-Loop triggered: task %d failed %d times — freezing",
            state["current_task_index"],
            escalation_count + 1,
        )
        return "freeze"

    return "architect"


def route_after_escalation_check(
    state: AutomatronState,
) -> Literal["human_review"]:
    """Route after freeze node — always goes to human_review for manual intervention."""
    return "human_review"
