"""Translation service for translating text via LLM."""

import logging
from typing import AsyncIterator, Union, Dict, Any

from src.api.services.model_config_service import ModelConfigService
from src.api.services.translation_config_service import TranslationConfigService

logger = logging.getLogger(__name__)


class TranslationService:
    """Service for translating text via LLM streaming."""

    def __init__(self):
        self.config_service = TranslationConfigService()

    async def translate_stream(
        self,
        text: str,
        target_language: str = None,
        model_id: str = None,
        use_input_target_language: bool = False,
    ) -> AsyncIterator[Union[str, Dict[str, Any]]]:
        """Translate text via LLM streaming.

        Args:
            text: Text to translate
            target_language: Override target language (defaults to config)
            model_id: Override model ID (defaults to config)
            use_input_target_language: If True, use input_target_language from config

        Yields:
            String tokens during streaming, or dict events at the end.
        """
        # Reload config to pick up latest changes
        self.config_service.reload_config()
        config = self.config_service.config

        # Determine target language (param > config)
        if target_language:
            effective_target_language = target_language
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

        # Get model and adapter
        model_service = ModelConfigService()
        model_config, provider_config = model_service.get_model_and_provider_sync(effective_model_id)

        adapter = model_service.get_adapter_for_provider(provider_config)

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
        )

        actual_model_id = f"{provider_config.id}:{model_config.id}"
        print(f"[TRANSLATE] Starting translation to {effective_target_language} (model: {actual_model_id})")
        logger.info(f"Translation started: target={effective_target_language}, model={actual_model_id}")

        from langchain_core.messages import HumanMessage as HMsg

        langchain_messages = [HMsg(content=prompt)]

        try:
            full_response = ""

            async for chunk in adapter.stream(llm, langchain_messages):
                if chunk.content:
                    full_response += chunk.content
                    yield chunk.content

            print(f"[TRANSLATE] Translation complete: {len(full_response)} chars")
            logger.info(f"Translation complete: {len(full_response)} chars")

            yield {
                "type": "translation_complete",
            }

        except Exception as e:
            print(f"[ERROR] Translation failed: {str(e)}")
            logger.error(f"Translation failed: {str(e)}", exc_info=True)
            yield {"type": "error", "error": str(e)}
