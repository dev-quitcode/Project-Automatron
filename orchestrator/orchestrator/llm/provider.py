"""LLM provider — model-agnostic wrapper around litellm."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

import litellm
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage, SystemMessage

from orchestrator.config import settings

logger = logging.getLogger(__name__)

# Suppress litellm debug logging
litellm.set_verbose = False


def _messages_to_dicts(messages: list[AnyMessage]) -> list[dict[str, str]]:
    """Convert LangChain messages to litellm dict format."""
    result = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": msg.content})
        else:
            result.append({"role": "user", "content": str(msg.content)})
    return result


async def call_llm(
    messages: list[AnyMessage],
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 8192,
) -> str:
    """Call LLM via litellm (non-streaming, returns full response).

    Args:
        messages: List of LangChain messages
        model: Model identifier (e.g., "claude-opus-4-20250918", "gpt-5.3-codex")
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response

    Returns:
        Full response text from the LLM
    """
    model = model or settings.architect_model
    msg_dicts = _messages_to_dicts(messages)

    logger.info("LLM call: model=%s, messages=%d", model, len(msg_dicts))

    try:
        response = await litellm.acompletion(
            model=model,
            messages=msg_dicts,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""

        # Log usage
        usage = response.usage
        if usage:
            logger.info(
                "LLM response: model=%s, input_tokens=%d, output_tokens=%d",
                model,
                usage.prompt_tokens,
                usage.completion_tokens,
            )

        return content

    except Exception as e:
        logger.error("LLM call failed (model=%s): %s", model, e)
        raise


async def call_llm_streaming(
    messages: list[AnyMessage],
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 8192,
) -> AsyncGenerator[str, None]:
    """Call LLM via litellm with streaming (yields tokens).

    Args:
        messages: List of LangChain messages
        model: Model identifier
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response

    Yields:
        Token strings as they arrive from the LLM
    """
    model = model or settings.architect_model
    msg_dicts = _messages_to_dicts(messages)

    logger.info("LLM streaming call: model=%s, messages=%d", model, len(msg_dicts))

    try:
        response = await litellm.acompletion(
            model=model,
            messages=msg_dicts,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    except Exception as e:
        logger.error("LLM streaming call failed (model=%s): %s", model, e)
        raise
