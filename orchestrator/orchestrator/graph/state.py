"""LangGraph State schema for the Automatron orchestrator."""

from __future__ import annotations

from typing import Annotated, Literal

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

# Phase literals
Phase = Literal["PLANNING", "SCAFFOLDING", "EXECUTING", "FROZEN", "COMPLETED"]

# Builder status literals
BuilderStatus = Literal["SUCCESS", "BLOCKER", "AMBIGUITY", "SILENT_DECISION", ""]


class AutomatronState(TypedDict):
    """Global state for the Automatron LangGraph state machine.

    This TypedDict is the single source of truth for the entire orchestration
    pipeline. Every node reads from and writes to this state.
    """

    # ── Project metadata ────────────────────────────────────────────────
    project_id: str
    project_name: str

    # ── PLAN.md content ─────────────────────────────────────────────────
    plan_md: str  # Raw PLAN.md content (frontmatter + body)
    stack_config: dict  # Parsed STACK_CONFIG.json

    # ── Current execution ───────────────────────────────────────────────
    current_task_index: int  # Index of current [ ] task
    current_task_text: str  # Full text of current task (title + context)
    total_tasks: int
    completed_tasks: int

    # ── Messages (Architect chat history) ───────────────────────────────
    messages: Annotated[list[AnyMessage], add_messages]

    # ── Builder output ──────────────────────────────────────────────────
    builder_status: BuilderStatus  # SUCCESS | BLOCKER | AMBIGUITY | SILENT_DECISION
    builder_output: str  # stdout/stderr from Cline
    builder_error_detail: str  # Error description for escalation

    # ── Anti-loop tracking ──────────────────────────────────────────────
    escalation_count: int  # Per-task escalation counter
    escalation_history: list[dict]  # [{task_index, status, timestamp}]

    # ── Docker ──────────────────────────────────────────────────────────
    container_id: str
    container_port: int

    # ── Phase tracking ──────────────────────────────────────────────────
    phase: Phase

    # ── Human intervention ──────────────────────────────────────────────
    requires_human: bool
    human_intervention_reason: str
