#!/usr/bin/env python3
"""
Z.ai (GLM) Provider
Uses OpenAI-compatible API for GLM-4.6 and other GLM models
"""

import os
from typing import List, Dict, Optional
from datetime import datetime
from ace.providers.base_provider import (
    BaseProvider, Model, ModelPricing, ProviderResponse
)


class ZaiProvider(BaseProvider):
    """Z.ai GLM provider using OpenAI-compatible API"""

    def _get_provider_name(self) -> str:
        return "zai"

    def _get_api_key(self) -> Optional[str]:
        return os.getenv("ZAI_API_KEY", "").strip() or None

    def get_pricing_url(self) -> str:
        return "https://z.ai/model-api"

    def fetch_pricing(self) -> Dict[str, ModelPricing]:
        """
        Fetch Z.ai pricing.
        For now, returns fallback pricing.
        """
        return self._get_fallback_pricing()

    def _get_fallback_pricing(self) -> Dict[str, ModelPricing]:
        """
        Fallback pricing for Z.ai models.
        Based on: https://openrouter.ai/z-ai/glm-4.6
        As of October 2025
        """
        now = datetime.now()

        return {
            "glm-4.6": ModelPricing(
                model="glm-4.6",
                input_cost_per_1m=0.60,
                output_cost_per_1m=2.00,
                context_window=200000,
                updated_at=now
            ),
            "glm-4.5-air": ModelPricing(
                model="glm-4.5-air",
                input_cost_per_1m=0.00,  # Free tier
                output_cost_per_1m=0.00,  # Free tier
                context_window=128000,
                updated_at=now
            ),
            "glm-4.5": ModelPricing(
                model="glm-4.5",
                input_cost_per_1m=0.50,
                output_cost_per_1m=1.50,
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
        """Call Z.ai API using OpenAI-compatible format"""
        if not self.is_configured():
            raise ValueError(
                "Z.ai API key not configured. "
                "Set ZAI_API_KEY environment variable. "
                "Get your key at: https://z.ai/model-api"
            )

        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package required for Z.ai provider. "
                "Install with: pip install openai"
            )

        # Create OpenAI client with Z.ai endpoint
        client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.z.ai/api/paas/v4"
        )

        # Call API (OpenAI-compatible)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
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
        """Get list of available Z.ai GLM models"""
        return [
            Model(
                name="glm-4.6",
                display_name="GLM-4.6",
                context_window=200000,
                description="Advanced coding, reasoning, and agentic capabilities. 5x cheaper than Claude.",
                supports_vision=False,
                supports_streaming=True
            ),
            Model(
                name="glm-4.5",
                display_name="GLM-4.5",
                context_window=128000,
                description="Previous flagship model with strong coding abilities",
                supports_vision=False,
                supports_streaming=True
            ),
            Model(
                name="glm-4.5-air",
                display_name="GLM-4.5 Air (Free)",
                context_window=128000,
                description="Free tier model, good for testing and light usage",
                supports_vision=False,
                supports_streaming=True
            ),
        ]
