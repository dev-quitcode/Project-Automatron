"""PLAN.md parser — extracts tasks, progress, and frontmatter from The Scripture."""

from __future__ import annotations

import re
from dataclasses import dataclass

import frontmatter


@dataclass
class Task:
    """A single task extracted from PLAN.md."""

    index: int  # Global index across all phases
    phase: str  # Phase name (e.g., "Фаза 1: Ініціалізація")
    title: str  # Task title (bold text after checkbox)
    description: str  # Full text including *Context* blocks
    line_number: int  # 1-based line number in PLAN.md


@dataclass
class Progress:
    """Progress summary from PLAN.md."""

    completed: int
    total: int

    @property
    def percentage(self) -> float:
        return (self.completed / self.total * 100) if self.total > 0 else 0.0


@dataclass
class PlanData:
    """Parsed PLAN.md data."""

    frontmatter: dict  # YAML frontmatter
    body: str  # Markdown body
    tasks: list[Task]
    progress: Progress


# ── Regex patterns ──────────────────────────────────────────────────────

# Matches: - [x] **Title**: Description  or  - [ ] **Title**: Description
CHECKBOX_PATTERN = re.compile(
    r"^(\s*)-\s*\[([ xX])\]\s*\*\*(.+?)\*\*[:\s]*(.*)",
    re.MULTILINE,
)

# Matches phase headers: ## Фаза 1: Something  or  ## Phase 1: Something
PHASE_PATTERN = re.compile(
    r"^##\s+(.+)$",
    re.MULTILINE,
)

# Matches context blocks:     - *Context*: ...
CONTEXT_PATTERN = re.compile(
    r"^\s+-\s*\*Context\*[:\s]*(.*)",
    re.MULTILINE,
)


def parse_plan(content: str) -> PlanData:
    """Parse PLAN.md content into structured PlanData.

    Extracts YAML frontmatter, tasks with checkboxes, phases, and progress.
    """
    post = frontmatter.loads(content)
    fm = dict(post.metadata)
    body = post.content

    tasks = _extract_tasks(content)
    completed = sum(1 for t in tasks if _is_completed_at_line(content, t.line_number))
    progress = Progress(completed=completed, total=len(tasks))

    return PlanData(
        frontmatter=fm,
        body=body,
        tasks=tasks,
        progress=progress,
    )


def _extract_tasks(content: str) -> list[Task]:
    """Extract all tasks (checkboxes) from PLAN.md."""
    lines = content.split("\n")
    tasks: list[Task] = []
    current_phase = ""
    task_index = 0

    for line_num, line in enumerate(lines, 1):
        # Track current phase
        phase_match = PHASE_PATTERN.match(line)
        if phase_match:
            current_phase = phase_match.group(1).strip()
            continue

        # Match checkbox
        checkbox_match = CHECKBOX_PATTERN.match(line)
        if checkbox_match:
            _indent, _status, title, desc_start = checkbox_match.groups()

            # Collect description including subsequent indented lines (context blocks)
            description_parts = [desc_start.strip()] if desc_start.strip() else []
            for next_line in lines[line_num:]:  # lines after current
                stripped = next_line.strip()
                if stripped.startswith("- *Context*"):
                    ctx_match = CONTEXT_PATTERN.match(next_line)
                    if ctx_match:
                        description_parts.append(f"Context: {ctx_match.group(1).strip()}")
                elif stripped.startswith("- ") and not stripped.startswith("- ["):
                    # Sub-item
                    description_parts.append(stripped[2:])
                elif stripped == "" or stripped.startswith("##") or CHECKBOX_PATTERN.match(next_line):
                    break
                else:
                    description_parts.append(stripped)

            tasks.append(
                Task(
                    index=task_index,
                    phase=current_phase,
                    title=title.strip(),
                    description="\n".join(description_parts),
                    line_number=line_num,
                )
            )
            task_index += 1

    return tasks


def _is_completed_at_line(content: str, line_number: int) -> bool:
    """Check if the task at the given line number is completed ([x])."""
    lines = content.split("\n")
    if 1 <= line_number <= len(lines):
        line = lines[line_number - 1]
        return bool(re.search(r"\[[ ]?[xX][ ]?\]", line))
    return False


def get_next_task(content: str) -> Task | None:
    """Find the first uncompleted task (- [ ]) in PLAN.md."""
    tasks = _extract_tasks(content)
    for task in tasks:
        if not _is_completed_at_line(content, task.line_number):
            return task
    return None


def get_progress(content: str) -> Progress:
    """Count completed vs total tasks in PLAN.md."""
    tasks = _extract_tasks(content)
    completed = sum(1 for t in tasks if _is_completed_at_line(content, t.line_number))
    return Progress(completed=completed, total=len(tasks))


def get_global_rules(content: str) -> list[str]:
    """Extract global_rules from PLAN.md YAML frontmatter."""
    try:
        post = frontmatter.loads(content)
        rules = post.metadata.get("global_rules", [])
        return rules if isinstance(rules, list) else []
    except Exception:
        return []


def mark_task_completed(content: str, task_index: int) -> str:
    """Mark a task checkbox as completed by global task index."""
    tasks = _extract_tasks(content)
    target = next((task for task in tasks if task.index == task_index), None)
    if target is None:
        return content

    lines = content.split("\n")
    line_idx = target.line_number - 1
    if not (0 <= line_idx < len(lines)):
        return content

    lines[line_idx] = re.sub(r"\[ \]", "[x]", lines[line_idx], count=1)
    return "\n".join(lines)
