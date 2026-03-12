"""Tests for graph routing decisions."""

from orchestrator.graph.edges import (
    MAX_ESCALATIONS,
    route_after_plan_review,
    route_after_status_classifier,
    route_after_task_selector,
)


def _make_state(**overrides):
    state = {
        "project_id": "test-123",
        "project_name": "Test Project",
        "current_task_index": 0,
        "builder_status": "",
        "escalation_count": 0,
        "container_id": "",
    }
    state.update(overrides)
    return state


def test_route_plan_review_to_repo_prepare_on_initial_approval():
    assert route_after_plan_review(_make_state(container_id="")) == "repo_prepare"


def test_route_plan_review_to_architect_when_resuming_after_freeze():
    assert route_after_plan_review(_make_state(container_id="container-1")) == "architect"


def test_route_task_selector_to_builder_when_tasks_remain():
    assert route_after_task_selector(_make_state(current_task_index=0)) == "builder"


def test_route_task_selector_to_preview_check_when_tasks_finish():
    assert route_after_task_selector(_make_state(current_task_index=-1)) == "preview_check"


def test_route_status_success_to_task_selector():
    assert route_after_status_classifier(_make_state(builder_status="SUCCESS")) == "task_selector"


def test_route_status_silent_decision_to_task_selector():
    assert (
        route_after_status_classifier(_make_state(builder_status="SILENT_DECISION"))
        == "task_selector"
    )


def test_route_status_repairable_failure_to_builder_retry():
    assert (
        route_after_status_classifier(
            _make_state(
                builder_status="BLOCKER",
                active_task_id="task-001",
                task_validation_result={"repairable": True, "escalate": False},
            )
        )
        == "builder"
    )


def test_route_status_blocker_to_architect_before_freeze_limit():
    assert (
        route_after_status_classifier(
            _make_state(builder_status="BLOCKER", escalation_count=MAX_ESCALATIONS - 1)
        )
        == "architect"
    )


def test_route_status_ambiguity_to_freeze_at_limit():
    assert (
        route_after_status_classifier(
            _make_state(builder_status="AMBIGUITY", escalation_count=MAX_ESCALATIONS)
        )
        == "freeze"
    )
