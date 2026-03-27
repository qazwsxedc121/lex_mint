"""Tests for minimal model capability fallback rules."""

from src.providers.model_capability_rules import (
    apply_model_capability_hints,
    infer_capability_overrides,
    infer_function_calling_support,
    infer_reasoning_controls,
    infer_reasoning_support,
    infer_requires_interleaved_thinking,
)


def test_local_qwen3_fallback_exposes_reasoning_function_calling_and_controls():
    model_id = "llm/qwen3-0.6b-q8_0.gguf"

    assert infer_reasoning_support(model_id, provider_id="local_gguf") is True
    assert infer_function_calling_support(model_id, provider_id="local_gguf") is True
    assert infer_requires_interleaved_thinking(model_id, provider_id="local_gguf") is None

    controls = infer_reasoning_controls(model_id, provider_id="local_gguf")
    assert controls is not None
    assert controls["mode"] == "toggle"
    assert controls["param"] == "enable_thinking"
    assert controls["options"] == []
    assert controls["default_option"] is None
    assert controls["disable_supported"] is True


def test_unknown_or_non_local_models_do_not_get_fallback_overrides():
    assert infer_capability_overrides("gpt-4o-mini", provider_id="openai") == {}
    assert infer_capability_overrides("deepseek-chat", provider_id="deepseek") == {}
    assert infer_reasoning_support("qwen3-32b", provider_id="openrouter") is None
    assert infer_function_calling_support("llm/qwen2.5-7b.gguf", provider_id="local_gguf") is None
    assert infer_reasoning_controls("google/gemini-2.5-flash", provider_id="openrouter") is None


def test_qwen35_local_model_does_not_match_qwen3_fallback():
    assert infer_capability_overrides("llm/qwen3.5-7b-instruct.gguf", provider_id="local_gguf") == {}
    assert infer_capability_overrides("llm/qwen35-7b-instruct.gguf", provider_id="local_gguf") == {}


def test_apply_model_capability_hints_preserves_explicit_capabilities():
    caps = {
        "reasoning": False,
        "function_calling": False,
        "reasoning_controls": None,
    }

    hinted = apply_model_capability_hints(
        "llm/qwen3-0.6b-q8_0.gguf",
        caps,
        provider_id="local_gguf",
    )

    assert hinted is not None
    assert hinted["reasoning"] is False
    assert hinted["function_calling"] is False
    assert hinted["reasoning_controls"] is None


def test_apply_model_capability_hints_backfills_missing_local_qwen3_capabilities():
    hinted = apply_model_capability_hints(
        "llm/qwen3-0.6b-q8_0.gguf",
        None,
        provider_defaults={"context_length": 32768, "streaming": True},
        provider_id="local_gguf",
    )

    assert hinted is not None
    assert hinted["context_length"] == 32768
    assert hinted["streaming"] is True
    assert hinted["reasoning"] is True
    assert hinted["function_calling"] is True
    assert hinted["reasoning_controls"]["param"] == "enable_thinking"


def test_apply_model_capability_hints_returns_none_when_no_caps_or_fallback():
    assert apply_model_capability_hints("gpt-4o-mini", None, provider_id="openai") is None
