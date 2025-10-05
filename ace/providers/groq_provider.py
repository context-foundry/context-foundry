#!/usr/bin/env python3
"""
Groq Provider
"""

import os
from typing import List, Dict, Optional
from datetime import datetime
from ace.providers.base_provider import (
    BaseProvider, Model, ModelPricing, ProviderResponse
)


class GroqProvider(BaseProvider):
    """Groq provider"""

    def _get_provider_name(self) -> str:
        return "groq"

    def _get_api_key(self) -> Optional[str]:
        return os.getenv("GROQ_API_KEY", "").strip() or None

    def get_pricing_url(self) -> str:
        return "https://groq.com/pricing"

    def fetch_pricing(self) -> Dict[str, ModelPricing]:
        """Fetch Groq pricing"""
        return self._get_fallback_pricing()

    def _get_fallback_pricing(self) -> Dict[str, ModelPricing]:
        """Fallback pricing for Groq models"""
        now = datetime.now()

        return {
            "llama-3.1-8b-instant": ModelPricing(
                model="llama-3.1-8b-instant",
                input_cost_per_1m=0.05,
                output_cost_per_1m=0.08,
                context_window=131072,
                updated_at=now
            ),
            "llama-3.1-70b-versatile": ModelPricing(
                model="llama-3.1-70b-versatile",
                input_cost_per_1m=0.59,
                output_cost_per_1m=0.79,
                context_window=131072,
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
        """Call Groq API"""
        if not self.is_configured():
            raise ValueError("Groq API key not configured. Set GROQ_API_KEY environment variable.")

        try:
            from groq import Groq
        except ImportError:
            raise ImportError("groq package required. Install with: pip install groq")

        client = Groq(api_key=self.api_key)

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
        """Get list of available Groq models"""
        return [
            Model(
                name="llama-3.1-8b-instant",
                display_name="Llama 3.1 8B",
                context_window=131072,
                description="Fast and affordable Llama model",
                supports_vision=False
            ),
            Model(
                name="llama-3.1-70b-versatile",
                display_name="Llama 3.1 70B",
                context_window=131072,
                description="More capable Llama model",
                supports_vision=False
            ),
        ]
