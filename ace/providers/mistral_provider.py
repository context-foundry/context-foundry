#!/usr/bin/env python3
"""
Mistral AI Provider
"""

import os
from typing import List, Dict, Optional
from datetime import datetime
from ace.providers.base_provider import (
    BaseProvider, Model, ModelPricing, ProviderResponse
)


class MistralProvider(BaseProvider):
    """Mistral AI provider"""

    def _get_provider_name(self) -> str:
        return "mistral"

    def _get_api_key(self) -> Optional[str]:
        return os.getenv("MISTRAL_API_KEY", "").strip() or None

    def get_pricing_url(self) -> str:
        return "https://mistral.ai/news/september-24-release"

    def fetch_pricing(self) -> Dict[str, ModelPricing]:
        """Fetch Mistral pricing"""
        return self._get_fallback_pricing()

    def _get_fallback_pricing(self) -> Dict[str, ModelPricing]:
        """Fallback pricing for Mistral models"""
        now = datetime.now()

        return {
            "codestral-latest": ModelPricing(
                model="codestral-latest",
                input_cost_per_1m=0.20,
                output_cost_per_1m=0.60,
                context_window=32000,
                updated_at=now
            ),
            "mistral-large-latest": ModelPricing(
                model="mistral-large-latest",
                input_cost_per_1m=2.00,
                output_cost_per_1m=6.00,
                context_window=128000,
                updated_at=now
            ),
        }

    def call_api(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 8000,
        temperature: float = 1.0,
        **kwargs
    ) -> ProviderResponse:
        """Call Mistral API"""
        if not self.is_configured():
            raise ValueError(
                "Mistral API key not configured. "
                "Set MISTRAL_API_KEY environment variable."
            )

        try:
            from mistralai.client import MistralClient
            from mistralai.models.chat_completion import ChatMessage
        except ImportError:
            raise ImportError(
                "mistralai package required. Install with: pip install mistralai"
            )

        client = MistralClient(api_key=self.api_key)

        # Convert messages
        mistral_messages = [
            ChatMessage(role=msg['role'], content=msg['content'])
            for msg in messages
        ]

        response = client.chat(
            model=model,
            messages=mistral_messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        return ProviderResponse(
            content=response.choices[0].message.content,
            model=response.model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            finish_reason=response.choices[0].finish_reason,
            raw_response=response
        )

    def get_available_models(self) -> List[Model]:
        """Get list of available Mistral models"""
        return [
            Model(
                name="codestral-latest",
                display_name="Codestral",
                context_window=32000,
                description="Code generation and completion specialist",
                supports_vision=False
            ),
            Model(
                name="mistral-large-latest",
                display_name="Mistral Large",
                context_window=128000,
                description="Most capable Mistral model",
                supports_vision=False
            ),
        ]
