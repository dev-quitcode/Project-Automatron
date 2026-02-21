"""Architect node — LLM-powered planning and re-planning."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import AIMessage, SystemMessage

from orchestrator.graph.state import AutomatronState
from orchestrator.llm.prompts import load_prompt
from orchestrator.llm.provider import call_llm

logger = logging.getLogger(__name__)


async def architect_node(state: AutomatronState) -> dict:
    """Architect node: generates or updates PLAN.md via LLM.

    Two operation modes:
    1. Initial Planning — no plan_md yet, generate from scratch via chat
    2. Re-planning (Escalation) — BLOCKER/AMBIGUITY received, revise the plan
    """
    project_name = state.get("project_name", "Project")
    plan_md = state.get("plan_md", "")
    builder_status = state.get("builder_status", "")
    builder_error = state.get("builder_error_detail", "")
    phase = state.get("phase", "PLANNING")

    # Determine mode
    is_escalation = builder_status in ("BLOCKER", "AMBIGUITY") and plan_md

    if is_escalation:
        logger.info(
            "Architect: RE-PLANNING mode (status=%s, task=%d)",
            builder_status,
            state.get("current_task_index", -1),
        )
        system_prompt = load_prompt("architect", state.get("architect_prompt_version", "v1"))
        escalation_context = (
            f"\n\n--- ESCALATION ---\n"
            f"Status: {builder_status}\n"
            f"Failed Task Index: {state.get('current_task_index', '?')}\n"
            f"Failed Task: {state.get('current_task_text', '?')}\n"
            f"Error Detail: {builder_error}\n"
            f"Builder Output (last 2000 chars):\n"
            f"{state.get('builder_output', '')[-2000:]}\n"
            f"--- END ESCALATION ---\n\n"
            f"Current PLAN.md:\n```markdown\n{plan_md}\n```\n\n"
            f"Please revise the failing task in PLAN.md to resolve the issue. "
            f"Return the full updated PLAN.md."
        )
        messages = list(state.get("messages", []))
        messages.append(SystemMessage(content=system_prompt))
        messages.append(AIMessage(content=escalation_context))
    else:
        logger.info("Architect: INITIAL PLANNING mode for '%s'", project_name)
        system_prompt = load_prompt("architect", "v1")
        messages = [SystemMessage(content=system_prompt)] + list(
            state.get("messages", [])
        )

    # Call LLM
    response_text = await call_llm(messages)

    # Parse response — extract PLAN.md and STACK_CONFIG.json
    new_plan_md = _extract_plan_md(response_text)
    stack_config = _extract_stack_config(response_text)

    result: dict = {
        "messages": [AIMessage(content=response_text)],
        "phase": "PLANNING",
    }

    if new_plan_md:
        result["plan_md"] = new_plan_md
    if stack_config:
        result["stack_config"] = stack_config

    # Reset escalation count on re-plan (architect provided new instructions)
    if is_escalation:
        result["escalation_count"] = state.get("escalation_count", 0) + 1

    logger.info("Architect: generated plan (%d chars)", len(new_plan_md or ""))
    return result


def _extract_plan_md(response: str) -> str | None:
    """Extract PLAN.md content from LLM response.

    Looks for content between ```markdown ... ``` or the full response
    if it starts with '---' (frontmatter).
    """
    # Try to find markdown code block
    if "```markdown" in response:
        start = response.index("```markdown") + len("```markdown")
        end = response.index("```", start)
        return response[start:end].strip()

    # If response starts with frontmatter, treat entire response as PLAN.md
    if response.strip().startswith("---"):
        return response.strip()

    return None


def _extract_stack_config(response: str) -> dict | None:
    """Extract STACK_CONFIG.json from LLM response.

    Looks for JSON code block with stack configuration.
    """
    if "```json" in response:
        try:
            start = response.index("```json") + len("```json")
            end = response.index("```", start)
            json_str = response[start:end].strip()
            config = json.loads(json_str)
            if "stack" in config or "framework" in config:
                return config
        except (ValueError, json.JSONDecodeError):
            pass
    return None
