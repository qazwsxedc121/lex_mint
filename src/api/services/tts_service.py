"""
TTS Service

Provides text-to-speech synthesis using Edge TTS.
"""
import re
import logging

import edge_tts

from .tts_config_service import TTSConfigService

logger = logging.getLogger(__name__)


class TTSService:
    """Service for text-to-speech synthesis using Edge TTS"""

    def __init__(self):
        self.config_service = TTSConfigService()

    def _sanitize_text(self, text: str) -> str:
        """Strip markdown/code/thinking blocks to plain speech text."""
        # Remove <think>...</think> blocks
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # Remove code fences (```...```)
        text = re.sub(r'```[\s\S]*?```', '', text)
        # Remove inline code (`...`)
        text = re.sub(r'`[^`]+`', '', text)
        # Remove image refs ![alt](url)
        text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
        # Remove markdown links [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
        # Remove bold/italic markers
        text = re.sub(r'[*_]{1,3}', '', text)
        # Remove strikethrough
        text = re.sub(r'~~', '', text)
        # Remove headings markers
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove blockquote markers
        text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
        # Remove horizontal rules
        text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
        # Remove list markers
        text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
        # Remove table formatting
        text = re.sub(r'\|', ' ', text)
        # Collapse multiple whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    def _detect_chinese(self, text: str) -> bool:
        """Detect if text is predominantly Chinese.

        Counts CJK Unified Ideograph characters vs total alphanumeric chars.
        If Chinese chars make up more than 30% of meaningful characters, treat as Chinese.
        """
        chinese_count = 0
        other_alpha_count = 0
        for ch in text:
            if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf':
                chinese_count += 1
            elif ch.isalpha():
                other_alpha_count += 1
        total = chinese_count + other_alpha_count
        if total == 0:
            return False
        return chinese_count / total > 0.3

    async def synthesize(self, text: str, voice: str = None, rate: str = None) -> bytes:
        """Synthesize text to audio bytes using edge-tts.

        Collects all audio data before returning so errors are caught
        before the HTTP response is sent.
        """
        self.config_service.reload_config()
        config = self.config_service.config

        effective_rate = rate or config.rate

        sanitized = self._sanitize_text(text)
        if not sanitized:
            raise ValueError("Text is empty after sanitization")

        if len(sanitized) > config.max_text_length:
            sanitized = sanitized[:config.max_text_length]

        # Auto-detect language and pick voice if not explicitly specified
        if voice:
            effective_voice = voice
        elif self._detect_chinese(sanitized):
            effective_voice = config.voice_zh
        else:
            effective_voice = config.voice

        logger.info(f"TTS synthesize: voice={effective_voice}, rate={effective_rate}, text_len={len(sanitized)}")

        communicate = edge_tts.Communicate(sanitized, effective_voice, rate=effective_rate, volume=config.volume)
        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        if not audio_chunks:
            raise RuntimeError("No audio data received from edge-tts")

        return b"".join(audio_chunks)
