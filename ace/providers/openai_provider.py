#!/usr/bin/env python3
"""
OpenAI (GPT) Provider
"""

import os
from typing import List, Dict, Optional
from datetime import datetime
from ace.providers.base_provider import (
    BaseProvider, Model, ModelPricing, ProviderResponse
)


class OpenAIProvider(BaseProvider):
    """OpenAI GPT provider"""

    def _get_provider_name(self) -> str:
        return "openai"

    def _get_api_key(self) -> Optional[str]:
        return os.getenv("OPENAI_API_KEY", "").strip() or None

    def get_pricing_url(self) -> str:
        return "https://openai.com/api/pricing/"

    def fetch_pricing(self) -> Dict[str, ModelPricing]:
        """
        Fetch OpenAI pricing.
        For now, returns fallback pricing.
        """
        # Use fallback pricing (manually updated)
        return self._get_fallback_pricing()

    def _get_fallback_pricing(self) -> Dict[str, ModelPricing]:
        """
        Fallback pricing for OpenAI models.
        Based on: https://openai.com/api/pricing/
        As of October 2025
        """
        now = datetime.now()

        return {
            "gpt-4o": ModelPricing(
                model="gpt-4o",
                input_cost_per_1m=2.50,
                output_cost_per_1m=10.00,
                context_window=128000,
                updated_at=now
            ),
            "gpt-4o-mini": ModelPricing(
                model="gpt-4o-mini",
                input_cost_per_1m=0.15,
                output_cost_per_1m=0.60,
                context_window=128000,
                updated_at=now
            ),
            "gpt-4-turbo": ModelPricing(
                model="gpt-4-turbo",
                input_cost_per_1m=10.00,
                output_cost_per_1m=30.00,
                context_window=128000,
                updated_at=now
            ),
            "gpt-4": ModelPricing(
                model="gpt-4",
                input_cost_per_1m=30.00,
                output_cost_per_1m=60.00,
                context_window=8192,
                updated_at=now
            ),
            "gpt-3.5-turbo": ModelPricing(
                model="gpt-3.5-turbo",
                input_cost_per_1m=0.50,
                output_cost_per_1m=1.50,
                context_window=16385,
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
        """Call OpenAI API"""
        if not self.is_configured():
            raise ValueError(
                "OpenAI API key not configured. "
                "Set OPENAI_API_KEY environment variable."
            )

        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package required. Install with: pip install openai"
            )

        client = OpenAI(api_key=self.api_key)

        # Call API
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
        """Get list of available OpenAI models"""
        return [
            Model(
                name="gpt-4o",
                display_name="GPT-4o",
                context_window=128000,
                description="Flagship model, multimodal, best overall performance",
                supports_vision=True
            ),
            Model(
                name="gpt-4o-mini",
                display_name="GPT-4o Mini",
                context_window=128000,
                description="Affordable and intelligent small model",
                supports_vision=True
            ),
            Model(
                name="gpt-4-turbo",
                display_name="GPT-4 Turbo",
                context_window=128000,
                description="Previous flagship model",
                supports_vision=True
            ),
            Model(
                name="gpt-4",
                display_name="GPT-4",
                context_window=8192,
                description="Original GPT-4",
                supports_vision=False
            ),
            Model(
                name="gpt-3.5-turbo",
                display_name="GPT-3.5 Turbo",
                context_window=16385,
                description="Fast and affordable",
                supports_vision=False
            ),
        ]
