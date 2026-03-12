from orchestrator.llm.catalog import (
    _normalize_anthropic_models,
    _normalize_google_models,
    _normalize_openai_models,
)


def test_normalize_openai_models_filters_non_generation_entries() -> None:
    payload = {
        "data": [
            {"id": "gpt-4.1"},
            {"id": "gpt-4.1-mini"},
            {"id": "text-embedding-3-large"},
            {"id": "whisper-1"},
            {"id": "omni-moderation-latest"},
        ]
    }

    models = _normalize_openai_models(payload)

    assert [item["id"] for item in models] == ["gpt-4.1", "gpt-4.1-mini"]


def test_normalize_anthropic_models_prefixes_provider() -> None:
    payload = {
        "data": [
            {"id": "claude-opus-4-20250918", "display_name": "Claude Opus 4"},
        ]
    }

    models = _normalize_anthropic_models(payload)

    assert models == [{"id": "anthropic/claude-opus-4-20250918", "label": "Claude Opus 4"}]


def test_normalize_google_models_keeps_generate_content_models() -> None:
    payload = {
        "models": [
            {
                "name": "models/gemini-2.5-pro",
                "displayName": "Gemini 2.5 Pro",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/embedding-001",
                "displayName": "Embedding 001",
                "supportedGenerationMethods": ["embedContent"],
            },
        ]
    }

    models = _normalize_google_models(payload)

    assert models == [{"id": "gemini/gemini-2.5-pro", "label": "Gemini 2.5 Pro"}]
