"""Translation service for translating text via LLM."""

import asyncio
import logging
from typing import AsyncIterator, Union, Dict, Any, Optional, List

from src.api.services.language_detection_service import LanguageDetectionService
from src.api.services.model_config_service import ModelConfigService
from src.api.services.translation_config_service import TranslationConfigService
from src.api.services.local_llama_cpp_service import LocalLlamaCppService
from src.api.services.think_tag_filter import ThinkTagStreamFilter
from src.providers.types import CallMode

logger = logging.getLogger(__name__)


class TranslationService:
    """Service for translating text via LLM streaming."""

    def __init__(self):
        self.config_service = TranslationConfigService()

    @classmethod
    def _resolve_auto_target_language(
        cls,
        text: str,
        config,
        detected_language: str | None = None,
    ) -> tuple[str | None, str | None]:
        """Auto route between configured language pair based on detected source language."""
        if detected_language is None:
            detected_raw, _, _ = LanguageDetectionService.detect_language(text)
            detected_language = LanguageDetectionService.normalize_language_hint(detected_raw)

        if detected_language is None:
            return None, None

        response_language_code = LanguageDetectionService.normalize_language_hint(
            config.target_language
        )
        input_language_code = LanguageDetectionService.normalize_language_hint(
            config.input_target_language
        )

        if not response_language_code or not input_language_code:
            return None, detected_language

        if response_language_code == input_language_code:
            return None, detected_language

        if detected_language == response_language_code:
            return config.input_target_language, detected_language
        if detected_language == input_language_code:
            return config.target_language, detected_language

        return None, detected_language

    async def translate_stream(
        self,
        text: str,
        target_language: Optional[str] = None,
        model_id: Optional[str] = None,
        use_input_target_language: bool = False,
        auto_detect_language: bool = True,
    ) -> AsyncIterator[Union[str, Dict[str, Any]]]:
        """Translate text via LLM streaming.

        Args:
            text: Text to translate
            target_language: Override target language (defaults to config)
            model_id: Override model ID (defaults to config)
            use_input_target_language: If True, use input_target_language from config
            auto_detect_language: If True, auto route between configured language pair

        Yields:
            String tokens during streaming, or dict events at the end.
        """
        # Reload config to pick up latest changes
        self.config_service.reload_config()
        config = self.config_service.config

        detected_language: str | None = None
        detected_confidence: float | None = None
        detector_name: str | None = None
        if auto_detect_language:
            detected_raw, detected_confidence, detector_name = (
                LanguageDetectionService.detect_language(text)
            )
            detected_language = LanguageDetectionService.normalize_language_hint(detected_raw)

        # Determine target language (explicit param > auto detect > legacy config path)
        if target_language:
            effective_target_language = target_language
        elif auto_detect_language:
            auto_target_language, _ = self._resolve_auto_target_language(
                text,
                config,
                detected_language=detected_language,
            )
            if auto_target_language:
                effective_target_language = auto_target_language
                logger.info(
                    "Auto language routing: detected=%s target=%s detector=%s conf=%s",
                    detected_language,
                    effective_target_language,
                    detector_name or "unknown",
                    f"{detected_confidence:.3f}" if detected_confidence is not None else "n/a",
                )
            else:
                effective_target_language = config.target_language
        elif use_input_target_language:
            effective_target_language = config.input_target_language
        else:
            effective_target_language = config.target_language

        # Determine model_id (param > config)
        effective_model_id = model_id or config.model_id

        # Build prompt from template
        prompt = config.prompt_template.format(
            text=text,
            target_language=effective_target_language,
        )

        if detected_language:
            yield {
                "type": "language_detected",
                "language": detected_language,
                "confidence": detected_confidence,
                "detector": detector_name,
            }

        if config.provider == "local_gguf":
            try:
                local_llm = LocalLlamaCppService(
                    model_path=config.local_gguf_model_path,
                    n_ctx=config.local_gguf_n_ctx,
                    n_threads=config.local_gguf_n_threads,
                    n_gpu_layers=config.local_gguf_n_gpu_layers,
                )
            except Exception as e:
                yield {"type": "error", "error": str(e)}
                return

            actual_model_id = f"local_gguf:{local_llm.model_path.name}"
            print(
                f"[TRANSLATE] Starting local GGUF translation to "
                f"{effective_target_language} (model: {actual_model_id})"
            )
            logger.info(
                "Local GGUF translation started: target=%s, model=%s",
                effective_target_language,
                actual_model_id,
            )

            try:
                full_response = ""
                think_filter = ThinkTagStreamFilter()
                for token in local_llm.stream_prompt(
                    prompt,
                    temperature=config.temperature,
                    max_tokens=config.local_gguf_max_tokens,
                ):
                    visible = think_filter.feed(token)
                    if visible:
                        full_response += visible
                        yield visible
                        await asyncio.sleep(0)

                tail = think_filter.flush()
                if tail:
                    full_response += tail
                    yield tail

                print(f"[TRANSLATE] Translation complete: {len(full_response)} chars")
                logger.info(f"Translation complete: {len(full_response)} chars")
                yield {
                    "type": "translation_complete",
                    "detected_source_language": detected_language,
                    "detected_source_confidence": detected_confidence,
                    "effective_target_language": effective_target_language,
                }
                return
            except Exception as e:
                print(f"[ERROR] Translation failed: {str(e)}")
                logger.error(f"Translation failed: {str(e)}", exc_info=True)
                yield {"type": "error", "error": str(e)}
                return

        # Get model and adapter
        model_service = ModelConfigService()
        model_config, provider_config = model_service.get_model_and_provider_sync(
            effective_model_id
        )

        adapter = model_service.get_adapter_for_provider(provider_config)
        resolved_call_mode = model_service.resolve_effective_call_mode(provider_config)
        effective_call_mode = (
            resolved_call_mode
            if isinstance(resolved_call_mode, CallMode)
            else CallMode.AUTO
        )
        allow_responses_fallback = effective_call_mode == CallMode.RESPONSES

        try:
            api_key = model_service.resolve_provider_api_key_sync(provider_config)
        except RuntimeError as e:
            yield {"type": "error", "error": str(e)}
            return

        # Create LLM instance
        llm = adapter.create_llm(
            model=model_config.id,
            base_url=provider_config.base_url,
            api_key=api_key,
            temperature=config.temperature,
            streaming=True,
            call_mode=effective_call_mode.value,
        )

        actual_model_id = f"{provider_config.id}:{model_config.id}"
        print(
            f"[TRANSLATE] Starting translation to {effective_target_language} "
            f"(model: {actual_model_id}, call_mode: {effective_call_mode.value})"
        )
        logger.info(
            "Translation started: target=%s, model=%s, call_mode=%s, responses_fallback=%s",
            effective_target_language,
            actual_model_id,
            effective_call_mode.value,
            allow_responses_fallback,
        )

        from langchain_core.messages import HumanMessage as HMsg, BaseMessage

        langchain_messages: List[BaseMessage] = [HMsg(content=prompt)]

        try:
            full_response = ""
            think_filter = ThinkTagStreamFilter()

            stream_kwargs = {"allow_responses_fallback": True} if allow_responses_fallback else {}
            async for chunk in adapter.stream(llm, langchain_messages, **stream_kwargs):
                if chunk.content:
                    visible = think_filter.feed(chunk.content)
                    if visible:
                        full_response += visible
                        yield visible

            tail = think_filter.flush()
            if tail:
                full_response += tail
                yield tail

            print(f"[TRANSLATE] Translation complete: {len(full_response)} chars")
            logger.info(f"Translation complete: {len(full_response)} chars")

            yield {
                "type": "translation_complete",
                "detected_source_language": detected_language,
                "detected_source_confidence": detected_confidence,
                "effective_target_language": effective_target_language,
            }

        except Exception as e:
            print(f"[ERROR] Translation failed: {str(e)}")
            logger.error(f"Translation failed: {str(e)}", exc_info=True)
            yield {"type": "error", "error": str(e)}
