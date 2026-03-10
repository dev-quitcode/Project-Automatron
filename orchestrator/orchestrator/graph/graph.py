"""LangGraph definition for the Automatron build workflow."""

from __future__ import annotations

import logging
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from orchestrator.config import settings
from orchestrator.graph.edges import (
    route_after_plan_review,
    route_after_status_classifier,
    route_after_task_selector,
)
from orchestrator.graph.nodes.architect import architect_node
from orchestrator.graph.nodes.builder import builder_node
from orchestrator.graph.nodes.reviewer import status_classifier_node
from orchestrator.graph.nodes.scaffold import (
    freeze_node,
    plan_review_node,
    preview_check_node,
    preview_review_node,
    ready_for_deploy_node,
    repo_prepare_node,
    scaffold_node,
    task_selector_node,
)
from orchestrator.graph.state import AutomatronState

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    builder = StateGraph(AutomatronState)

    builder.add_node("architect", architect_node)
    builder.add_node("plan_review", plan_review_node)
    builder.add_node("repo_prepare", repo_prepare_node)
    builder.add_node("scaffold", scaffold_node)
    builder.add_node("task_selector", task_selector_node)
    builder.add_node("builder", builder_node)
    builder.add_node("status_classifier", status_classifier_node)
    builder.add_node("freeze", freeze_node)
    builder.add_node("preview_check", preview_check_node)
    builder.add_node("preview_review", preview_review_node)
    builder.add_node("ready_for_deploy", ready_for_deploy_node)

    builder.add_edge(START, "architect")
    builder.add_edge("architect", "plan_review")
    builder.add_conditional_edges("plan_review", route_after_plan_review)
    builder.add_edge("repo_prepare", "scaffold")
    builder.add_edge("scaffold", "task_selector")
    builder.add_conditional_edges("task_selector", route_after_task_selector)
    builder.add_edge("builder", "status_classifier")
    builder.add_conditional_edges("status_classifier", route_after_status_classifier)
    builder.add_edge("freeze", "plan_review")
    builder.add_edge("preview_check", "preview_review")
    builder.add_edge("preview_review", "ready_for_deploy")
    builder.add_edge("ready_for_deploy", END)

    return builder


def compile_graph(checkpointer: SqliteSaver | None = None):
    graph_builder = build_graph()

    if checkpointer is None:
        db_path = Path(settings.checkpoint_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        checkpointer = SqliteSaver.from_conn_string(str(db_path))

    graph = graph_builder.compile(checkpointer=checkpointer)
    logger.info("Automatron graph compiled")
    return graph
