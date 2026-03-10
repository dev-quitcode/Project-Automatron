"""Conditional edge functions for the Automatron graph."""

from __future__ import annotations

import logging
from typing import Literal

from orchestrator.graph.state import AutomatronState

logger = logging.getLogger(__name__)

MAX_ESCALATIONS = 2


def route_after_plan_review(state: AutomatronState) -> Literal["repo_prepare", "architect"]:
    if state.get("container_id"):
        logger.info("Plan review resume after freeze -> architect")
        return "architect"
    logger.info("Initial plan review approved -> repo_prepare")
    return "repo_prepare"


def route_after_task_selector(state: AutomatronState) -> Literal["builder", "preview_check"]:
    if state["current_task_index"] < 0:
        logger.info("All tasks completed -> preview_check")
        return "preview_check"
    logger.info("Task %d selected -> builder", state["current_task_index"])
    return "builder"


def route_after_status_classifier(
    state: AutomatronState,
) -> Literal["task_selector", "freeze", "architect"]:
    status = state["builder_status"]

    if status in ("SUCCESS", "SILENT_DECISION"):
        return "task_selector"

    escalation_count = state.get("escalation_count", 0)
    if escalation_count >= MAX_ESCALATIONS:
        logger.error("Task %d exceeded escalation limit", state["current_task_index"])
        return "freeze"

    return "architect"
