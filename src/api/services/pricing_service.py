"""
Pricing Service for LLM Token Cost Calculation

Provides pricing configuration and cost calculation for different LLM providers and models.
"""
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from src.providers.types import TokenUsage, CostInfo

logger = logging.getLogger(__name__)


class PricingService:
    """Service for calculating LLM token costs."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize pricing service.

        Args:
            config_path: Path to models_config.yaml containing pricing info
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "models_config.yaml"
        self.config_path = config_path
        self._pricing_cache: Optional[Dict[str, Any]] = None

    def _load_pricing(self) -> Dict[str, Any]:
        """Load pricing configuration from yaml file."""
        if self._pricing_cache is not None:
            return self._pricing_cache

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self._pricing_cache = data.get("pricing", {})
        except Exception as e:
            logger.warning(f"Failed to load pricing config: {e}")
            self._pricing_cache = {}

        return self._pricing_cache or {}

    def get_pricing(
        self,
        provider_id: str,
        model_id: str
    ) -> Dict[str, float]:
        """
        Get pricing for a specific provider/model combination.

        Args:
            provider_id: Provider ID (e.g., "deepseek", "openrouter")
            model_id: Model ID (e.g., "deepseek-chat", "gpt-4o")

        Returns:
            Dict with input_price_per_1m and output_price_per_1m
        """
        pricing = self._load_pricing()

        # Get provider pricing
        provider_pricing = pricing.get(provider_id, {})

        # Try specific model first
        if model_id in provider_pricing:
            return provider_pricing[model_id]

        # Fall back to default for provider
        if "default" in provider_pricing:
            return provider_pricing["default"]

        # No pricing info available
        return {
            "input_price_per_1m": 0.0,
            "output_price_per_1m": 0.0
        }

    def calculate_cost(
        self,
        provider_id: str,
        model_id: str,
        usage: Optional[TokenUsage]
    ) -> CostInfo:
        """
        Calculate cost for a given token usage.

        Args:
            provider_id: Provider ID
            model_id: Model ID
            usage: Token usage information

        Returns:
            CostInfo with calculated costs
        """
        if usage is None:
            return CostInfo()

        pricing = self.get_pricing(provider_id, model_id)

        input_price = pricing.get("input_price_per_1m", 0.0)
        output_price = pricing.get("output_price_per_1m", 0.0)

        # Calculate costs (price is per 1M tokens)
        input_cost = (usage.prompt_tokens / 1_000_000) * input_price
        output_cost = (usage.completion_tokens / 1_000_000) * output_price
        total_cost = input_cost + output_cost

        return CostInfo(
            input_cost=round(input_cost, 8),
            output_cost=round(output_cost, 8),
            total_cost=round(total_cost, 8),
            currency="USD"
        )

    def clear_cache(self):
        """Clear the pricing cache to reload from file."""
        self._pricing_cache = None
