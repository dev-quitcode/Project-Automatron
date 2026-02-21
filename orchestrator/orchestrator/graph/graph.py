"""LangGraph StateGraph definition — the core orchestration graph."""

from __future__ import annotations

import logging
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from orchestrator.config import settings
from orchestrator.graph.edges import (
    route_after_escalation_check,
    route_after_status_classifier,
    route_after_task_selector,
)
from orchestrator.graph.nodes.architect import architect_node
from orchestrator.graph.nodes.builder import builder_node
from orchestrator.graph.nodes.reviewer import status_classifier_node
from orchestrator.graph.nodes.scaffold import (
    completion_node,
    freeze_node,
    human_review_node,
    scaffold_node,
    task_selector_node,
)
from orchestrator.graph.state import AutomatronState

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Build the Automatron state graph (without compilation).

    Returns the StateGraph builder so callers can compile with their
    desired checkpointer.
    """
    builder = StateGraph(AutomatronState)

    # ── Register nodes ──────────────────────────────────────────────────
    builder.add_node("architect", architect_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("scaffold", scaffold_node)
    builder.add_node("task_selector", task_selector_node)
    builder.add_node("builder", builder_node)
    builder.add_node("status_classifier", status_classifier_node)
    builder.add_node("freeze", freeze_node)
    builder.add_node("completion", completion_node)

    # ── Edges ───────────────────────────────────────────────────────────
    # START → architect (planning phase)
    builder.add_edge(START, "architect")

    # architect → human_review (interrupt for approval)
    builder.add_edge("architect", "human_review")

    # human_review → scaffold (after human approves PLAN.md)
    builder.add_edge("human_review", "scaffold")

    # scaffold → task_selector
    builder.add_edge("scaffold", "task_selector")

    # task_selector → builder OR completion (conditional)
    builder.add_conditional_edges("task_selector", route_after_task_selector)

    # builder → status_classifier
    builder.add_edge("builder", "status_classifier")

    # status_classifier → task_selector OR escalation_check (conditional)
    builder.add_conditional_edges("status_classifier", route_after_status_classifier)

    # escalation_check is embedded in route_after_escalation_check
    # which routes to: architect (re-plan) OR freeze (anti-loop)
    builder.add_conditional_edges("freeze", route_after_escalation_check)

    # freeze → END (after human resumes interrupt, goes to human_review)
    # Actually freeze uses interrupt(), so after resume it continues
    # We route freeze back to human_review for re-planning
    # This is handled by the edge from freeze

    # completion → END
    builder.add_edge("completion", END)

    return builder


def compile_graph(checkpointer: SqliteSaver | None = None):
    """Compile the graph with optional checkpointer.

    If no checkpointer is provided, creates one from settings.
    """
    graph_builder = build_graph()

    if checkpointer is None:
        # Ensure data directory exists
        db_path = Path(settings.checkpoint_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        checkpointer = SqliteSaver.from_conn_string(str(db_path))

    graph = graph_builder.compile(checkpointer=checkpointer)
    logger.info("Automatron graph compiled successfully")
    return graph
