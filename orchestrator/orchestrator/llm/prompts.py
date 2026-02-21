"""Prompt loader — loads prompt templates from files."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# Prompts directory (relative to the orchestrator package root)
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


@lru_cache(maxsize=32)
def load_prompt(name: str, version: str = "v1") -> str:
    """Load a prompt template from the prompts directory.

    Args:
        name: Prompt name (e.g., "architect", "builder", "reviewer")
        version: Prompt version (e.g., "v1")

    Returns:
        Prompt text content

    Raises:
        FileNotFoundError: If prompt file does not exist
    """
    filename = f"{name}_{version}.txt"
    filepath = PROMPTS_DIR / filename

    if not filepath.exists():
        logger.error("Prompt file not found: %s", filepath)
        raise FileNotFoundError(f"Prompt file not found: {filepath}")

    content = filepath.read_text(encoding="utf-8")
    logger.debug("Loaded prompt: %s (%d chars)", filename, len(content))
    return content
