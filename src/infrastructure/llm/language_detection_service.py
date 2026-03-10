"""Language detection helpers used by translation features."""

from __future__ import annotations

import re
from typing import Optional, Tuple

try:
    from langdetect import DetectorFactory, LangDetectException, detect_langs

    DetectorFactory.seed = 0
    _LANGDETECT_AVAILABLE = True
except Exception:
    LangDetectException = Exception  # type: ignore[assignment]
    _LANGDETECT_AVAILABLE = False


class LanguageDetectionService:
    """Detect source language and normalize language hints."""

    _EN_CHAR_RE = re.compile(r"[A-Za-z]")
    _ZH_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
    _BCP47_RE = re.compile(r"^[a-z]{2,3}(?:[-_][a-z0-9]{2,8})?$", re.IGNORECASE)

    _LANGUAGE_ALIASES = {
        "english": "en",
        "chinese": "zh",
        "mandarin": "zh",
        "japanese": "ja",
        "korean": "ko",
        "french": "fr",
        "spanish": "es",
        "german": "de",
        "russian": "ru",
        "portuguese": "pt",
        "italian": "it",
        "arabic": "ar",
        "hindi": "hi",
        "thai": "th",
        "vietnamese": "vi",
        "indonesian": "id",
        "turkish": "tr",
    }

    _LANGUAGE_KEYWORDS = {
        "simplified chinese": "zh",
        "traditional chinese": "zh",
        "\u4e2d\u6587": "zh",
        "\u6c49\u8bed": "zh",
        "\u6f22\u8a9e": "zh",
        "\u82f1\u6587": "en",
        "\u82f1\u8bed": "en",
        "\u65e5\u6587": "ja",
        "\u65e5\u8bed": "ja",
        "\u97e9\u6587": "ko",
        "\u97e9\u8bed": "ko",
        "\u6cd5\u6587": "fr",
        "\u897f\u73ed\u7259\u8bed": "es",
        "\u5fb7\u6587": "de",
        "\u4fc4\u6587": "ru",
    }

    @classmethod
    def normalize_language_hint(cls, language: str | None) -> Optional[str]:
        """Normalize language hint/name/locale to short language code."""
        if not language:
            return None

        value = language.strip()
        lowered = value.lower()

        if cls._BCP47_RE.match(lowered):
            return lowered.split("-")[0].split("_")[0]

        if lowered in cls._LANGUAGE_ALIASES:
            return cls._LANGUAGE_ALIASES[lowered]

        for keyword, code in cls._LANGUAGE_KEYWORDS.items():
            if keyword in lowered or keyword in value:
                return code

        for alias, code in cls._LANGUAGE_ALIASES.items():
            if alias in lowered:
                return code

        return None

    @classmethod
    def _detect_with_heuristic(cls, text: str) -> Optional[str]:
        """Fallback detector for zh/en when langdetect is unavailable."""
        zh_count = len(cls._ZH_CHAR_RE.findall(text))
        en_count = len(cls._EN_CHAR_RE.findall(text))

        if zh_count == 0 and en_count == 0:
            return None

        if zh_count >= 2 and zh_count >= en_count:
            return "zh"
        if en_count >= 4 and en_count >= zh_count * 2:
            return "en"
        if zh_count > en_count * 1.2:
            return "zh"
        if en_count > zh_count * 1.2:
            return "en"

        return None

    @classmethod
    def detect_language(cls, text: str) -> Tuple[Optional[str], Optional[float], str]:
        """Return (language_code, confidence, detector_name)."""
        cleaned = (text or "").strip()
        if not cleaned:
            return None, None, "none"

        if _LANGDETECT_AVAILABLE:
            try:
                candidates = detect_langs(cleaned)
                if candidates:
                    top = candidates[0]
                    return top.lang.lower(), float(top.prob), "langdetect"
            except LangDetectException:
                pass
            except Exception:
                pass

        fallback = cls._detect_with_heuristic(cleaned)
        if fallback:
            return fallback, None, "heuristic"

        return None, None, "none"
