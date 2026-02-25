"""Tests for model capability inference rules."""

from src.providers.model_capability_rules import (
    apply_model_capability_hints,
    infer_capability_overrides,
    infer_reasoning_support,
    infer_requires_interleaved_thinking,
)


def test_infer_requires_interleaved_thinking_for_kimi_and_deepseek_variants():
    assert infer_requires_interleaved_thinking("kimi-k2.5") is True
    assert infer_requires_interleaved_thinking("moonshotai/kimi-k2.5:free") is True
    assert infer_requires_interleaved_thinking("deepseek-chat") is True
    assert infer_requires_interleaved_thinking("openrouter/deepseek-reasoner") is True


def test_infer_requires_interleaved_thinking_returns_none_for_unknown_models():
    assert infer_requires_interleaved_thinking("qwen3-32b") is None
    assert infer_requires_interleaved_thinking("gpt-4o-mini") is None


def test_infer_reasoning_support_for_kimi_and_deepseek_variants():
    assert infer_reasoning_support("deepseek-chat") is True
    assert infer_reasoning_support("moonshotai/kimi-k2.5:free") is True
    assert infer_reasoning_support("gpt-4o-mini") is None


def test_infer_capability_overrides_include_reasoning_and_interleaved():
    overrides = infer_capability_overrides("deepseek-r1")
    assert overrides["reasoning"] is True
    assert overrides["requires_interleaved_thinking"] is True


def test_apply_interleaved_hint_preserves_explicit_capability_override():
    caps = {"requires_interleaved_thinking": False, "reasoning": True}
    hinted = apply_model_capability_hints("kimi-k2.5", caps)
    assert hinted["requires_interleaved_thinking"] is False
    assert hinted["reasoning"] is True


def test_apply_interleaved_hint_uses_provider_defaults_when_capabilities_missing():
    hinted = apply_model_capability_hints(
        "deepseek-chat",
        None,
        provider_defaults={"context_length": 64000, "reasoning": True},
    )
    assert hinted["context_length"] == 64000
    assert hinted["requires_interleaved_thinking"] is True


def test_apply_interleaved_hint_overrides_provider_default_false():
    hinted = apply_model_capability_hints(
        "kimi-k2.5",
        None,
        provider_defaults={"requires_interleaved_thinking": False, "reasoning": True},
    )
    assert hinted["requires_interleaved_thinking"] is True
    assert hinted["reasoning"] is True


def test_apply_model_capability_hints_returns_none_when_no_rules_or_caps():
    hinted = apply_model_capability_hints("gpt-4o-mini", None)
    assert hinted is None
