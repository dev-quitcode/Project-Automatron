"""Architect node — LLM-powered planning and re-planning."""

from __future__ import annotations

import json
import logging
import uuid

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from orchestrator.api.websocket import emit_architect_message, emit_plan_updated
from orchestrator.graph.state import AutomatronState
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
    is_escalation = builder_status in ("BLOCKER", "AMBIGUITY") and bool(plan_md)

    if is_escalation:
        system_prompt = load_prompt("architect", state.get("architect_prompt_version", "v1"))
        escalation_context = (
            f"Current failing task index: {state.get('current_task_index', '?')}\n"
            f"Task: {state.get('current_task_text', '')}\n"
            f"Status: {builder_status}\n"
            f"Error detail: {builder_error}\n"
            f"Builder output:\n{state.get('builder_output', '')[-2000:]}\n\n"
            f"Return the full updated PLAN.md and STACK_CONFIG.json if needed.\n"
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
        messages = [SystemMessage(content=system_prompt)] + list(state.get("messages", []))
        if not any(isinstance(message, HumanMessage) for message in messages):
            messages.append(HumanMessage(content=intake_text))

    response_text = await call_llm(messages)
    new_plan_md = _extract_plan_md(response_text)
    stack_config = _extract_stack_config(response_text)

    await save_chat_message(str(uuid.uuid4()), project_id, "architect", response_text)
    await emit_architect_message(project_id, response_text, streaming=False)

    result: dict = {
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
    if is_escalation:
        result["escalation_count"] = state.get("escalation_count", 0) + 1

    logger.info("Architect generated plan for %s (%d chars)", project_name, len(new_plan_md or ""))
    return result


def _extract_plan_md(response: str) -> str | None:
    if "```markdown" in response:
        start = response.index("```markdown") + len("```markdown")
        end = response.index("```", start)
        return response[start:end].strip()

    if response.strip().startswith("---"):
        return response.strip()

    return None


def _extract_stack_config(response: str) -> dict | None:
    if "```json" not in response:
        return None

    try:
        start = response.index("```json") + len("```json")
        end = response.index("```", start)
        config = json.loads(response[start:end].strip())
        if isinstance(config, dict):
            return config
    except (ValueError, json.JSONDecodeError):
        logger.warning("Failed to parse STACK_CONFIG.json from architect response")
    return None
