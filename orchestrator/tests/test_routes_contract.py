"""Tests for execution contract related API routes."""

from __future__ import annotations

import pytest

from orchestrator.api import routes


@pytest.mark.asyncio
async def test_api_get_execution_contract(monkeypatch):
    async def fake_get_required_project(project_id: str) -> dict[str, object]:
        return {
            "id": project_id,
            "contract_version": 2,
            "execution_contract": {"task_graph": [{"task_id": "task-001"}]},
        }

    monkeypatch.setattr(routes, "_get_required_project", fake_get_required_project)

    result = await routes.api_get_execution_contract("project-1")

    assert result["project_id"] == "project-1"
    assert result["contract_version"] == 2
    assert result["execution_contract"]["task_graph"][0]["task_id"] == "task-001"


@pytest.mark.asyncio
async def test_api_get_decision_log(monkeypatch):
    async def fake_get_required_project(project_id: str) -> dict[str, object]:
        return {
            "id": project_id,
            "contract_version": 4,
            "decision_log": [{"id": "decision-001"}],
            "plan_delta_history": [{"type": "plan_delta"}],
        }

    monkeypatch.setattr(routes, "_get_required_project", fake_get_required_project)

    result = await routes.api_get_decision_log("project-1")

    assert result["contract_version"] == 4
    assert result["decision_log"][0]["id"] == "decision-001"
    assert result["plan_delta_history"][0]["type"] == "plan_delta"


@pytest.mark.asyncio
async def test_api_get_task_status(monkeypatch):
    async def fake_get_required_project(project_id: str) -> dict[str, object]:
        return {"id": project_id}

    async def fake_get_task_status(project_id: str) -> dict[str, object]:
        return {
            "project_id": project_id,
            "active_task_id": "task-002",
            "active_task": {"task_id": "task-002"},
            "completed_tasks": 1,
            "total_tasks": 2,
            "task_attempt_count": 2,
            "task_validation_result": {"blocking": True},
            "builder_report": {"status": "failed"},
            "last_escalation": {"task_id": "task-002"},
        }

    monkeypatch.setattr(routes, "_get_required_project", fake_get_required_project)
    monkeypatch.setattr(routes, "runner_get_task_status", fake_get_task_status)

    result = await routes.api_get_task_status("project-1")

    assert result["active_task_id"] == "task-002"
    assert result["completed_tasks"] == 1
    assert result["builder_report"]["status"] == "failed"
