"""Architect node — LLM-powered planning and re-planning."""

from __future__ import annotations

import json
import logging
import uuid

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from orchestrator.api.websocket import emit_architect_message, emit_plan_updated
from orchestrator.execution_contract import (
    append_plan_delta_history,
    build_execution_contract,
    extract_execution_contract,
    extract_json_blocks,
    extract_plan_delta,
)
from orchestrator.graph.state import AutomatronState
from orchestrator.llm.configuration import default_llm_config, normalize_llm_config
from orchestrator.llm.prompts import load_prompt
from orchestrator.llm.provider import call_llm
from orchestrator.models.project import save_chat_message

logger = logging.getLogger(__name__)


async def architect_node(state: AutomatronState) -> dict:
    """Generate or revise the technical plan."""
    project_id = state["project_id"]
    project_name = state.get("project_name", "Project")
    plan_md = state.get("plan_md", "")
    builder_status = state.get("builder_status", "")
    builder_error = state.get("builder_error_detail", "")
    llm_config = normalize_llm_config(state.get("llm_config") or default_llm_config())
    architect_model = llm_config["architect"]["model"]
    is_escalation = builder_status in ("BLOCKER", "AMBIGUITY") and bool(plan_md)

    if is_escalation:
        system_prompt = load_prompt("architect", state.get("architect_prompt_version", "v1"))
        escalation_context = (
            f"Current failing task index: {state.get('current_task_index', '?')}\n"
            f"Task: {state.get('current_task_text', '')}\n"
            f"Task ID: {state.get('active_task_id', '')}\n"
            f"Status: {builder_status}\n"
            f"Error detail: {builder_error}\n"
            f"Builder output:\n{state.get('builder_output', '')[-2000:]}\n\n"
            f"Last escalation:\n{json.dumps(state.get('last_escalation', {}), ensure_ascii=True)}\n\n"
            "Return an updated PLAN.md, STACK_CONFIG.json if needed, execution_contract.json, "
            "and plan_delta.json describing only the changed tasks/decisions.\n"
            f"Existing PLAN.md:\n```markdown\n{plan_md}\n```"
        )
        messages = list(state.get("messages", []))
        messages.extend(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=escalation_context),
            ]
        )
    else:
        system_prompt = load_prompt("architect", "v1")
        intake_text = state.get("intake_text", "")
        messages = [
            SystemMessage(
                content=(
                    f"{system_prompt}\n\n"
                    "You must not stop at clarifying questions. "
                    "If requirements are ambiguous, choose sensible MVP defaults and still return "
                    "a complete PLAN.md, STACK_CONFIG.json, and execution_contract.json."
                )
            )
        ] + list(state.get("messages", []))
        if not any(isinstance(message, HumanMessage) for message in messages):
            messages.append(HumanMessage(content=intake_text))

    response_text = await call_llm(messages, model=architect_model)
    new_plan_md = _extract_plan_md(response_text)
    stack_config = _extract_stack_config(response_text)
    execution_contract = extract_execution_contract(response_text)
    plan_delta = extract_plan_delta(response_text)
    if not new_plan_md:
        response_text, new_plan_md, stack_config, execution_contract, plan_delta = await _repair_architect_output(
            response_text=response_text,
            intake_text=state.get("intake_text", ""),
            plan_md=plan_md,
            stack_config=stack_config,
            architect_model=architect_model,
            existing_execution_contract=state.get("execution_contract", {}),
        )

    if new_plan_md:
        execution_contract = execution_contract or build_execution_contract(
            project_name=project_name,
            intake_text=state.get("intake_text", ""),
            plan_md=new_plan_md,
            stack_config=stack_config or state.get("stack_config", {}),
            existing_contract=state.get("execution_contract", {}),
        )
    else:
        execution_contract = execution_contract or state.get("execution_contract", {})

    contract_version = int(state.get("contract_version", 0) or 0) + 1
    decision_log = execution_contract.get("decision_log", state.get("decision_log", [])) if execution_contract else state.get("decision_log", [])
    plan_delta_history = append_plan_delta_history(state.get("plan_delta_history", []), plan_delta)
    next_task = None
    if execution_contract and isinstance(execution_contract.get("task_graph"), list):
        for task in execution_contract["task_graph"]:
            if not task.get("completed"):
                next_task = task
                break

    await save_chat_message(str(uuid.uuid4()), project_id, "architect", response_text)
    await emit_architect_message(project_id, response_text, streaming=False)

    if is_escalation:
        result: dict = {
            "messages": [AIMessage(content=response_text)],
            "project_stage": "building",
            "status": "building",
            "requires_human": False,
            "human_intervention_reason": "",
            "task_attempt_count": 0,
            "task_validation_result": {},
        }
    else:
        result = {
            "messages": [AIMessage(content=response_text)],
            "project_stage": "awaiting_plan_approval",
            "status": "planning",
            "requires_human": True,
            "human_intervention_reason": "Review and approve the generated technical plan.",
        }

    if new_plan_md:
        result["plan_md"] = new_plan_md
        await emit_plan_updated(project_id, new_plan_md)
    if stack_config:
        result["stack_config"] = stack_config
    if execution_contract:
        result["execution_contract"] = execution_contract
        result["contract_version"] = contract_version
        result["decision_log"] = decision_log
        result["plan_delta_history"] = plan_delta_history
    if next_task:
        result["active_task_id"] = next_task.get("task_id", "")
    if is_escalation:
        result["escalation_count"] = state.get("escalation_count", 0) + 1
        result["last_escalation"] = {}

    logger.info("Architect generated plan for %s (%d chars)", project_name, len(new_plan_md or ""))
    return result


async def _repair_architect_output(
    *,
    response_text: str,
    intake_text: str,
    plan_md: str,
    stack_config: dict | None,
    architect_model: str,
    existing_execution_contract: dict | None,
) -> tuple[str, str | None, dict | None, dict | None, dict | None]:
    repair_prompt = (
        "Convert the material below into a valid Automatron planning response.\n"
        "Return ONLY:\n"
        "1. A full PLAN.md inside a ```markdown block\n"
        "2. A STACK_CONFIG.json inside a ```json block\n"
        "3. An execution_contract.json inside a ```json block\n"
        "Do not ask clarifying questions. If details are missing, choose sensible MVP defaults.\n\n"
        f"Raw intake:\n{intake_text}\n\n"
        f"Previous response:\n{response_text}\n\n"
        f"Existing PLAN.md:\n{plan_md}\n"
    )
    repair_response = await call_llm(
        [
            SystemMessage(content="You repair architect outputs into valid PLAN.md and STACK_CONFIG.json."),
            HumanMessage(content=repair_prompt),
        ],
        model=architect_model,
    )
    repaired_plan_md = _extract_plan_md(repair_response)
    repaired_stack_config = _extract_stack_config(repair_response) or stack_config
    repaired_execution_contract = extract_execution_contract(repair_response) or existing_execution_contract
    repaired_plan_delta = extract_plan_delta(repair_response)
    if repaired_plan_md:
        return (
            repair_response,
            repaired_plan_md,
            repaired_stack_config,
            repaired_execution_contract,
            repaired_plan_delta,
        )
    return response_text, plan_md or None, stack_config, existing_execution_contract, None


def _extract_plan_md(response: str) -> str | None:
    if "```markdown" in response:
        start = response.index("```markdown") + len("```markdown")
        end = response.index("```", start)
        return response[start:end].strip()

    if response.strip().startswith("---"):
        return response.strip()

    return None


def _extract_stack_config(response: str) -> dict | None:
    for config in extract_json_blocks(response):
        if "stack" in config and any(key in config for key in ("framework", "port", "package_manager")):
            return config
    if "```json" in response:
        logger.warning("Failed to parse STACK_CONFIG.json from architect response")
    return None
