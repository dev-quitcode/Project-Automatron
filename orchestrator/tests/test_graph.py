"""Tests for LangGraph state and edges."""

from orchestrator.graph.edges import (
    MAX_ESCALATIONS,
    route_after_status_classifier,
    route_after_task_selector,
)


def _make_state(**overrides):
    """Create a minimal AutomatronState dict for testing."""
    defaults = {
        "project_id": "test-123",
        "project_name": "Test",
        "plan_md": "",
        "stack_config": {},
        "current_task_index": 0,
        "current_task_text": "Test task",
        "total_tasks": 5,
        "completed_tasks": 0,
        "messages": [],
        "builder_status": "",
        "builder_output": "",
        "builder_error_detail": "",
        "escalation_count": 0,
        "escalation_history": [],
        "container_id": "abc123",
        "container_port": 7001,
        "phase": "EXECUTING",
        "requires_human": False,
        "human_intervention_reason": "",
    }
    defaults.update(overrides)
    return defaults


def test_route_task_selector_to_builder():
    state = _make_state(current_task_index=0)
    assert route_after_task_selector(state) == "builder"


def test_route_task_selector_to_completion():
    state = _make_state(current_task_index=-1)
    assert route_after_task_selector(state) == "completion"


def test_route_status_success_to_task_selector():
    state = _make_state(builder_status="SUCCESS")
    assert route_after_status_classifier(state) == "task_selector"


def test_route_status_silent_decision_to_task_selector():
    state = _make_state(builder_status="SILENT_DECISION")
    assert route_after_status_classifier(state) == "task_selector"


def test_route_status_blocker_low_escalation_to_architect():
    state = _make_state(builder_status="BLOCKER", escalation_count=0)
    assert route_after_status_classifier(state) == "architect"


def test_route_status_blocker_high_escalation_to_freeze():
    state = _make_state(
        builder_status="BLOCKER", escalation_count=MAX_ESCALATIONS
    )
    assert route_after_status_classifier(state) == "freeze"


def test_route_status_ambiguity_to_architect():
    state = _make_state(builder_status="AMBIGUITY", escalation_count=1)
    assert route_after_status_classifier(state) == "architect"


def test_route_status_ambiguity_high_escalation_to_freeze():
    state = _make_state(
        builder_status="AMBIGUITY", escalation_count=MAX_ESCALATIONS
    )
    assert route_after_status_classifier(state) == "freeze"
