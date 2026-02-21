"""Tests for the Architect node (mocked LLM)."""

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
