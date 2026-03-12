"""Dynamic LLM model catalog fetched from provider APIs."""

from __future__ import annotations

import time
from typing import Any

import httpx

from orchestrator.config import settings
from orchestrator.llm.configuration import LlmProvider, SUPPORTED_PROVIDERS

CACHE_TTL_SECONDS = 300
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"
GOOGLE_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"

_catalog_cache: dict[str, dict[str, Any]] = {}


def _now_epoch() -> float:
    return time.time()


def _supports_text_generation_openai(model_id: str) -> bool:
    normalized = model_id.lower()
    allowed_prefixes = ("gpt-", "chatgpt-", "o1", "o3", "o4", "codex-")
    blocked_keywords = (
        "audio",
        "transcribe",
        "tts",
        "moderation",
        "embedding",
        "embed",
        "image",
        "whisper",
        "search",
        "realtime",
        "vision-preview",
        "instruct",
    )
    return normalized.startswith(allowed_prefixes) and not any(
        keyword in normalized for keyword in blocked_keywords
    )


def _normalize_openai_models(payload: dict[str, Any]) -> list[dict[str, str]]:
    models: list[dict[str, str]] = []
    for item in payload.get("data", []):
        model_id = str(item.get("id") or "").strip()
        if not model_id or not _supports_text_generation_openai(model_id):
            continue
        models.append({"id": model_id, "label": model_id})
    return sorted(models, key=lambda item: item["label"].lower())


def _normalize_anthropic_models(payload: dict[str, Any]) -> list[dict[str, str]]:
    models: list[dict[str, str]] = []
    for item in payload.get("data", []):
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue
        display_name = str(item.get("display_name") or model_id).strip()
        models.append({"id": f"anthropic/{model_id}", "label": display_name})
    return sorted(models, key=lambda item: item["label"].lower())


def _normalize_google_models(payload: dict[str, Any]) -> list[dict[str, str]]:
    models: list[dict[str, str]] = []
    for item in payload.get("models", []):
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        supported_actions = item.get("supportedActions") or item.get("supported_actions") or []
        supported_generation_methods = (
            item.get("supportedGenerationMethods")
            or item.get("supported_generation_methods")
            or []
        )
        if not any(action == "generateContent" for action in supported_actions) and not any(
            action == "generateContent" for action in supported_generation_methods
        ):
            continue
        model_name = name.removeprefix("models/")
        display_name = str(item.get("displayName") or item.get("display_name") or model_name).strip()
        models.append({"id": f"gemini/{model_name}", "label": display_name})
    return sorted(models, key=lambda item: item["label"].lower())


async def _fetch_openai_models() -> list[dict[str, str]]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            OPENAI_MODELS_URL,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        )
        response.raise_for_status()
        return _normalize_openai_models(response.json())


async def _fetch_anthropic_models() -> list[dict[str, str]]:
    models: list[dict[str, str]] = []
    after_id: str | None = None

    async with httpx.AsyncClient(timeout=20.0) as client:
        for _ in range(5):
            params = {"after_id": after_id} if after_id else None
            response = await client.get(
                ANTHROPIC_MODELS_URL,
                params=params,
                headers={
                    "anthropic-version": "2023-06-01",
                    "X-Api-Key": settings.anthropic_api_key,
                },
            )
            response.raise_for_status()
            payload = response.json()
            models.extend(_normalize_anthropic_models(payload))
            if not payload.get("has_more"):
                break
            after_id = payload.get("last_id")
            if not after_id:
                break

    deduped = {item["id"]: item for item in models}
    return sorted(deduped.values(), key=lambda item: item["label"].lower())


async def _fetch_google_models() -> list[dict[str, str]]:
    models: list[dict[str, str]] = []
    page_token: str | None = None

    async with httpx.AsyncClient(timeout=20.0) as client:
        for _ in range(5):
            params = {"key": settings.google_api_key, "pageSize": 1000}
            if page_token:
                params["pageToken"] = page_token
            response = await client.get(GOOGLE_MODELS_URL, params=params)
            response.raise_for_status()
            payload = response.json()
            models.extend(_normalize_google_models(payload))
            page_token = payload.get("nextPageToken")
            if not page_token:
                break

    deduped = {item["id"]: item for item in models}
    return sorted(deduped.values(), key=lambda item: item["label"].lower())


async def _fetch_provider_models(provider: LlmProvider) -> list[dict[str, str]]:
    if provider == "anthropic":
        return await _fetch_anthropic_models()
    if provider == "google":
        return await _fetch_google_models()
    return await _fetch_openai_models()


def _provider_configured(provider: LlmProvider) -> bool:
    if provider == "anthropic":
        return bool(settings.anthropic_api_key)
    if provider == "google":
        return bool(settings.google_api_key)
    return bool(settings.openai_api_key)


async def get_provider_model_catalog(
    provider: str,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    normalized_provider = provider.strip().lower()
    if normalized_provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")

    typed_provider = normalized_provider  # type: ignore[assignment]
    configured = _provider_configured(typed_provider)
    cached = _catalog_cache.get(typed_provider)
    now = _now_epoch()

    if not force_refresh and cached and now - cached["fetched_at_epoch"] < CACHE_TTL_SECONDS:
        return {
            "provider": typed_provider,
            "configured": configured,
            "models": cached["models"],
            "fetched_at": cached["fetched_at"],
            "error": cached.get("error"),
            "cached": True,
        }

    if not configured:
        payload = {
            "provider": typed_provider,
            "configured": False,
            "models": [],
            "fetched_at": None,
            "error": "Provider API key is not configured",
            "cached": False,
        }
        _catalog_cache[typed_provider] = {
            "models": [],
            "fetched_at": None,
            "fetched_at_epoch": now,
            "error": payload["error"],
        }
        return payload

    try:
        models = await _fetch_provider_models(typed_provider)
        fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        _catalog_cache[typed_provider] = {
            "models": models,
            "fetched_at": fetched_at,
            "fetched_at_epoch": now,
            "error": None,
        }
        return {
            "provider": typed_provider,
            "configured": True,
            "models": models,
            "fetched_at": fetched_at,
            "error": None,
            "cached": False,
        }
    except Exception as exc:
        error = str(exc)
        if cached:
            return {
                "provider": typed_provider,
                "configured": True,
                "models": cached["models"],
                "fetched_at": cached["fetched_at"],
                "error": error,
                "cached": True,
            }
        return {
            "provider": typed_provider,
            "configured": True,
            "models": [],
            "fetched_at": None,
            "error": error,
            "cached": False,
        }


async def get_all_provider_model_catalogs(*, force_refresh: bool = False) -> list[dict[str, Any]]:
    return [
        await get_provider_model_catalog(provider, force_refresh=force_refresh)
        for provider in SUPPORTED_PROVIDERS
    ]
