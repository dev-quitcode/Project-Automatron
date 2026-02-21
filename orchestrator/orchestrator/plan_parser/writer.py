"""PLAN.md writer — modifies PLAN.md content (mark tasks, update sections)."""

from __future__ import annotations

import re


def mark_task_complete(content: str, task_index: int) -> str:
    """Mark the task at the given index as completed: [ ] → [x].

    Args:
        content: Raw PLAN.md content
        task_index: Zero-based global task index

    Returns:
        Updated PLAN.md content with the task marked [x]
    """
    lines = content.split("\n")
    checkbox_pattern = re.compile(r"^(\s*-\s*)\[[ ]\](\s*\*\*.+?\*\*.*)")
    current_index = 0

    for i, line in enumerate(lines):
        match = checkbox_pattern.match(line)
        if match:
            if current_index == task_index:
                prefix, rest = match.groups()
                lines[i] = f"{prefix}[x]{rest}"
                break
            current_index += 1

    return "\n".join(lines)


def unmark_task(content: str, task_index: int) -> str:
    """Unmark a completed task: [x] → [ ].

    Args:
        content: Raw PLAN.md content
        task_index: Zero-based global task index

    Returns:
        Updated PLAN.md content with the task unmarked
    """
    lines = content.split("\n")
    checkbox_pattern = re.compile(r"^(\s*-\s*)\[[xX]\](\s*\*\*.+?\*\*.*)")
    completed_pattern = re.compile(r"^(\s*-\s*)\[[ xX]\](\s*\*\*.+?\*\*.*)")
    current_index = 0

    for i, line in enumerate(lines):
        if completed_pattern.match(line):
            if current_index == task_index:
                match = re.match(r"^(\s*-\s*)\[[xX]\](\s*\*\*.+?\*\*.*)", line)
                if match:
                    prefix, rest = match.groups()
                    lines[i] = f"{prefix}[ ]{rest}"
                break
            current_index += 1

    return "\n".join(lines)


def update_task_description(
    content: str, task_index: int, new_description: str
) -> str:
    """Update the description/context of a specific task.

    Args:
        content: Raw PLAN.md content
        task_index: Zero-based global task index
        new_description: New description text (replaces existing)

    Returns:
        Updated PLAN.md content
    """
    lines = content.split("\n")
    checkbox_pattern = re.compile(r"^(\s*)-\s*\[[ xX]\]\s*\*\*(.+?)\*\*[:\s]*(.*)")
    current_index = 0

    for i, line in enumerate(lines):
        match = checkbox_pattern.match(line)
        if match:
            if current_index == task_index:
                indent, title, _old_desc = match.groups()
                checkbox_char = "x" if re.search(r"\[[xX]\]", line) else " "

                # Remove old sub-lines (context, sub-items)
                end = i + 1
                while end < len(lines):
                    next_line = lines[end].strip()
                    if (
                        next_line == ""
                        or next_line.startswith("##")
                        or re.match(r"^\s*-\s*\[[ xX]\]", lines[end])
                    ):
                        break
                    end += 1

                # Build new task lines
                new_lines = [
                    f"{indent}- [{checkbox_char}] **{title}**: {new_description}"
                ]
                lines[i:end] = new_lines
                break
            current_index += 1

    return "\n".join(lines)
