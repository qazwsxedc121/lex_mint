"""
LLM Adapters

This package contains SDK adapters for different LLM providers.
"""

from typing import Any

from .anthropic_adapter import AnthropicAdapter
from .bailian_adapter import BailianAdapter
from .deepseek_adapter import DeepSeekAdapter
from .gemini_adapter import GeminiAdapter
from .kimi_adapter import KimiAdapter
from .local_gguf_adapter import LocalGgufAdapter
from .ollama_adapter import OllamaAdapter
from .openai_adapter import OpenAIAdapter
from .openrouter_adapter import OpenRouterAdapter
from .siliconflow_adapter import SiliconFlowAdapter
from .volcengine_adapter import VolcEngineAdapter
from .xai_adapter import XAIAdapter
from .zhipu_adapter import ZhipuAdapter

LMSTUDIO_IMPORT_ERROR = None
LmStudioAdapter: type[Any] | None
try:
    from .lmstudio_adapter import LmStudioAdapter as _LmStudioAdapter
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("lmstudio"):
        LmStudioAdapter = None
        LMSTUDIO_IMPORT_ERROR = exc
    else:
        raise
else:
    LmStudioAdapter = _LmStudioAdapter

__all__ = [
    "OpenAIAdapter",
    "OpenRouterAdapter",
    "DeepSeekAdapter",
    "AnthropicAdapter",
    "OllamaAdapter",
    "XAIAdapter",
    "ZhipuAdapter",
    "VolcEngineAdapter",
    "GeminiAdapter",
    "BailianAdapter",
    "SiliconFlowAdapter",
    "KimiAdapter",
    "LocalGgufAdapter",
]

if LmStudioAdapter is not None:
    __all__.append("LmStudioAdapter")
