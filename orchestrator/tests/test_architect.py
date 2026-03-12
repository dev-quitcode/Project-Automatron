"""Tests for the Architect node (mocked LLM)."""

from orchestrator.execution_contract import extract_execution_contract, extract_plan_delta
from orchestrator.graph.nodes.architect import _extract_plan_md, _extract_stack_config


SAMPLE_RESPONSE_WITH_PLAN = """\
Here is the plan for your project:

```markdown
---
project_name: "MyApp"
stack: "Next.js + Tailwind"
global_rules:
  - "Use TypeScript"
---

# Plan

## Phase 1
- [ ] **Init**: Initialize project.
```

And the stack config:

```json
{
  "stack": "nextjs",
  "framework": "Next.js 15",
  "port": 3000,
  "init_script": "init-nextjs.sh"
}
```

And the execution contract:

```json
{
  "project_meta": {
    "name": "MyApp"
  },
  "task_graph": [
    {
      "task_id": "task-001",
      "title": "Init",
      "done_when": ["Build passes"],
      "validation_commands": ["npm run build"],
      "allowed_autonomy": ["fix_compile_errors"],
      "escalate_if": ["requires_schema_redesign"]
    }
  ]
}
```

And a plan delta:

```json
{
  "type": "plan_delta",
  "changed_task_ids": ["task-001"]
}
```
"""


def test_extract_plan_md_from_markdown_block():
    plan = _extract_plan_md(SAMPLE_RESPONSE_WITH_PLAN)
    assert plan is not None
    assert "project_name" in plan
    assert "MyApp" in plan
    assert "- [ ] **Init**" in plan


def test_extract_plan_md_from_frontmatter():
    raw = "---\nproject_name: Test\n---\n\n# Plan\n- [ ] **Task**: Do it."
    plan = _extract_plan_md(raw)
    assert plan is not None
    assert "project_name" in plan


def test_extract_plan_md_returns_none():
    plan = _extract_plan_md("No plan here, just text.")
    assert plan is None


def test_extract_stack_config():
    config = _extract_stack_config(SAMPLE_RESPONSE_WITH_PLAN)
    assert config is not None
    assert config["stack"] == "nextjs"
    assert config["port"] == 3000
    assert config["init_script"] == "init-nextjs.sh"


def test_extract_stack_config_returns_none():
    config = _extract_stack_config("No JSON here.")
    assert config is None


def test_extract_execution_contract():
    contract = extract_execution_contract(SAMPLE_RESPONSE_WITH_PLAN)
    assert contract is not None
    assert contract["project_meta"]["name"] == "MyApp"
    assert contract["task_graph"][0]["task_id"] == "task-001"


def test_extract_plan_delta():
    plan_delta = extract_plan_delta(SAMPLE_RESPONSE_WITH_PLAN)
    assert plan_delta is not None
    assert plan_delta["type"] == "plan_delta"
    assert plan_delta["changed_task_ids"] == ["task-001"]
