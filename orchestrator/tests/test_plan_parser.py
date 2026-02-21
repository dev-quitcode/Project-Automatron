"""Tests for the PLAN.md parser."""

from orchestrator.plan_parser.parser import (
    get_global_rules,
    get_next_task,
    get_progress,
    parse_plan,
)
from orchestrator.plan_parser.writer import mark_task_complete, unmark_task

SAMPLE_PLAN = """\
---
project_name: "TestProject"
stack: "Next.js + Tailwind"
root_dir: "/workspace"
global_rules:
  - "STRICT: Use TypeScript. No 'any'."
  - "STRICT: All API calls via Server Actions."
---

# План Реалізації: TestProject

## Фаза 1: Ініціалізація
- [x] **Scaffold Project**: Initialize Next.js. Clean `globals.css`.
- [ ] **Setup Database**: Create client in `src/lib/db.ts`.
    - *Context*: Use `pg` driver. Connection via ENV `DATABASE_URL`.

## Фаза 2: Core Logic
- [ ] **Auth Module**: Create login form.
    - *Context*: Use Zod for validation.
- [ ] **API Routes**: Create REST endpoints.
"""


def test_parse_plan_extracts_frontmatter():
    data = parse_plan(SAMPLE_PLAN)
    assert data.frontmatter["project_name"] == "TestProject"
    assert data.frontmatter["stack"] == "Next.js + Tailwind"
    assert len(data.frontmatter["global_rules"]) == 2


def test_parse_plan_extracts_tasks():
    data = parse_plan(SAMPLE_PLAN)
    assert len(data.tasks) == 4
    assert data.tasks[0].title == "Scaffold Project"
    assert data.tasks[1].title == "Setup Database"
    assert data.tasks[2].title == "Auth Module"
    assert data.tasks[3].title == "API Routes"


def test_parse_plan_tracks_phases():
    data = parse_plan(SAMPLE_PLAN)
    assert "Фаза 1" in data.tasks[0].phase
    assert "Фаза 2" in data.tasks[2].phase


def test_progress_counts():
    progress = get_progress(SAMPLE_PLAN)
    assert progress.completed == 1
    assert progress.total == 4
    assert progress.percentage == 25.0


def test_get_next_task_finds_first_uncompleted():
    task = get_next_task(SAMPLE_PLAN)
    assert task is not None
    assert task.title == "Setup Database"
    assert task.index == 1
    assert "pg" in task.description


def test_get_next_task_returns_none_when_all_completed():
    all_done = SAMPLE_PLAN.replace("[ ]", "[x]")
    task = get_next_task(all_done)
    assert task is None


def test_get_global_rules():
    rules = get_global_rules(SAMPLE_PLAN)
    assert len(rules) == 2
    assert "TypeScript" in rules[0]


def test_mark_task_complete():
    updated = mark_task_complete(SAMPLE_PLAN, 1)  # Setup Database
    assert "[x] **Setup Database**" in updated
    progress = get_progress(updated)
    assert progress.completed == 2


def test_unmark_task():
    updated = unmark_task(SAMPLE_PLAN, 0)  # Scaffold Project
    assert "[ ] **Scaffold Project**" in updated
    progress = get_progress(updated)
    assert progress.completed == 0
