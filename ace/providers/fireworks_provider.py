#!/usr/bin/env python3
"""
Fireworks AI Provider
"""

import os
from typing import List, Dict, Optional
from datetime import datetime
from ace.providers.base_provider import (
    BaseProvider, Model, ModelPricing, ProviderResponse
)


class FireworksProvider(BaseProvider):
    """Fireworks AI provider"""

    def _get_provider_name(self) -> str:
        return "fireworks"

    def _get_api_key(self) -> Optional[str]:
        return os.getenv("FIREWORKS_API_KEY", "").strip() or None

    def get_pricing_url(self) -> str:
        return "https://fireworks.ai/models/fireworks/starcoder2-7b"

    def fetch_pricing(self) -> Dict[str, ModelPricing]:
        """Fetch Fireworks AI pricing"""
        return self._get_fallback_pricing()

    def _get_fallback_pricing(self) -> Dict[str, ModelPricing]:
        """Fallback pricing for Fireworks models"""
        now = datetime.now()

        return {
            "accounts/fireworks/models/starcoder2-7b": ModelPricing(
                model="accounts/fireworks/models/starcoder2-7b",
                input_cost_per_1m=0.20,
                output_cost_per_1m=0.20,
                context_window=16384,
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
        """Call Fireworks AI API"""
        if not self.is_configured():
            raise ValueError(
                "Fireworks API key not configured. "
                "Set FIREWORKS_API_KEY environment variable."
            )

        try:
            import requests
        except ImportError:
            raise ImportError("requests package required. Install with: pip install requests")

        url = "https://api.fireworks.ai/inference/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()

        data = response.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})

        return ProviderResponse(
            content=choice["message"]["content"],
            model=data.get("model", model),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop"),
            raw_response=data
        )

    def get_available_models(self) -> List[Model]:
        """Get list of available Fireworks models"""
        return [
            Model(
                name="accounts/fireworks/models/starcoder2-7b",
                display_name="StarCoder2 7B",
                context_window=16384,
                description="Code generation model",
                supports_vision=False
            ),
        ]
