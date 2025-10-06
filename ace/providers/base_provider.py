#!/usr/bin/env python3
"""
Base Provider Interface
All AI providers implement this interface for unified access
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class Model:
    """Model metadata"""
    name: str
    display_name: str
    context_window: int
    description: str = ""
    supports_vision: bool = False
    supports_streaming: bool = True


@dataclass
class ModelPricing:
    """Pricing information for a model"""
    model: str
    input_cost_per_1m: float  # Cost per 1M input tokens
    output_cost_per_1m: float  # Cost per 1M output tokens
    context_window: int
    updated_at: datetime


@dataclass
class ProviderResponse:
    """Unified response from any provider"""
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    finish_reason: str = "stop"
    raw_response: Optional[Any] = None


class BaseProvider(ABC):
    """
    Abstract base class for all AI providers.
    Each provider implements this interface.
    """

    def __init__(self):
        self.name = self._get_provider_name()
        self.api_key = self._get_api_key()

    @abstractmethod
    def _get_provider_name(self) -> str:
        """Return provider name (e.g., 'anthropic', 'openai')"""
        pass

    @abstractmethod
    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment"""
        pass

    @abstractmethod
    def get_pricing_url(self) -> str:
        """Return URL to provider's pricing documentation"""
        pass

    @abstractmethod
    def fetch_pricing(self) -> Dict[str, ModelPricing]:
        """
        Fetch current pricing for all models.
        Should scrape/fetch from pricing URL.

        Returns:
            Dict mapping model name to pricing info
        """
        pass

    @abstractmethod
    def call_api(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 8000,
        temperature: float = 1.0,
        **kwargs
    ) -> ProviderResponse:
        """
        Make API call to the provider.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Provider-specific parameters

        Returns:
            ProviderResponse with unified format
        """
        pass

    @abstractmethod
    def get_available_models(self) -> List[Model]:
        """
        Get list of available models.

        Returns:
            List of Model objects
        """
        pass

    def validate_model(self, model: str) -> bool:
        """Check if model is available from this provider"""
        available = [m.name for m in self.get_available_models()]
        return model in available

    def is_configured(self) -> bool:
        """Check if provider has valid API key"""
        return self.api_key is not None and len(self.api_key.strip()) > 0

    def get_display_name(self) -> str:
        """Get human-readable provider name"""
        name_map = {
            'anthropic': 'Anthropic (Claude)',
            'openai': 'OpenAI (GPT)',
            'gemini': 'Google (Gemini)',
            'groq': 'Groq',
            'cloudflare': 'Cloudflare Workers AI',
            'fireworks': 'Fireworks AI',
            'mistral': 'Mistral AI',
            'zai': 'Z.ai (GLM)',
            'github': 'GitHub Models (FREE)'
        }
        return name_map.get(self.name, self.name.title())
