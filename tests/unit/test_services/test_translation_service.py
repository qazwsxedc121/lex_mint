"""Unit tests for TranslationService language routing helpers."""

from src.api.services.language_detection_service import LanguageDetectionService
from src.api.services.translation_config_service import TranslationConfig
from src.api.services.translation_service import TranslationService


def _build_config(
    target_language: str = "Chinese",
    input_target_language: str = "English",
) -> TranslationConfig:
    return TranslationConfig(
        enabled=True,
        target_language=target_language,
        input_target_language=input_target_language,
        provider="model_config",
        model_id="deepseek:deepseek-chat",
        local_gguf_model_path="models/llm/local-translate.gguf",
        local_gguf_n_ctx=8192,
        local_gguf_n_threads=0,
        local_gguf_n_gpu_layers=0,
        local_gguf_max_tokens=2048,
        temperature=0.3,
        timeout_seconds=30,
        prompt_template="{text}",
    )


def test_normalize_language_hint_supports_common_languages():
    assert LanguageDetectionService.normalize_language_hint("English") == "en"
    assert LanguageDetectionService.normalize_language_hint("Chinese") == "zh"
    assert LanguageDetectionService.normalize_language_hint("Japanese") == "ja"
    assert LanguageDetectionService.normalize_language_hint("fr-FR") == "fr"


def test_detect_language_returns_en_for_english_text():
    detected, _, _ = LanguageDetectionService.detect_language("Please translate this sentence.")
    assert LanguageDetectionService.normalize_language_hint(detected) == "en"


def test_detect_language_returns_zh_for_chinese_text():
    detected, _, _ = LanguageDetectionService.detect_language(
        (
            "\u8fd9\u662f\u4e00\u6bb5\u9700\u8981\u8bc6\u522b\u8bed\u8a00"
            "\u7684\u4e2d\u6587\u5185\u5bb9\u3002"
        )
    )
    assert LanguageDetectionService.normalize_language_hint(detected) == "zh"


def test_auto_target_routes_english_text_to_configured_chinese():
    config = _build_config(target_language="Chinese", input_target_language="English")

    target_language, detected_language = TranslationService._resolve_auto_target_language(
        "This message is written in English.",
        config,
        detected_language="en",
    )

    assert detected_language == "en"
    assert target_language == "Chinese"


def test_auto_target_routes_chinese_text_to_configured_english():
    config = _build_config(target_language="Chinese", input_target_language="English")

    target_language, detected_language = TranslationService._resolve_auto_target_language(
        "\u4f60\u597d\uff0c\u8fd9\u662f\u4e00\u6761\u4e2d\u6587\u6d88\u606f\u3002",
        config,
        detected_language="zh",
    )

    assert detected_language == "zh"
    assert target_language == "English"


def test_auto_target_routes_for_non_chinese_language_pair():
    config = _build_config(target_language="Japanese", input_target_language="English")

    target_language, detected_language = TranslationService._resolve_auto_target_language(
        "This text should be routed to Japanese.",
        config,
        detected_language="en",
    )

    assert detected_language == "en"
    assert target_language == "Japanese"


def test_auto_target_skips_when_detected_language_not_in_pair():
    config = _build_config(target_language="Japanese", input_target_language="English")

    target_language, detected_language = TranslationService._resolve_auto_target_language(
        "Bonjour tout le monde.",
        config,
        detected_language="fr",
    )

    assert detected_language == "fr"
    assert target_language is None
