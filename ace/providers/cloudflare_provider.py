#!/usr/bin/env python3
"""
Cloudflare Workers AI Provider
"""

import os
from typing import List, Dict, Optional
from datetime import datetime
from ace.providers.base_provider import (
    BaseProvider, Model, ModelPricing, ProviderResponse
)


class CloudflareProvider(BaseProvider):
    """Cloudflare Workers AI provider"""

    def _get_provider_name(self) -> str:
        return "cloudflare"

    def _get_api_key(self) -> Optional[str]:
        return os.getenv("CLOUDFLARE_API_KEY", "").strip() or None

    def get_pricing_url(self) -> str:
        return "https://developers.cloudflare.com/workers-ai/models/qwen2.5-coder-32b-instruct/"

    def fetch_pricing(self) -> Dict[str, ModelPricing]:
        """Fetch Cloudflare Workers AI pricing"""
        return self._get_fallback_pricing()

    def _get_fallback_pricing(self) -> Dict[str, ModelPricing]:
        """Fallback pricing for Cloudflare models"""
        now = datetime.now()

        return {
            "@cf/qwen/qwen2.5-coder-32b-instruct": ModelPricing(
                model="@cf/qwen/qwen2.5-coder-32b-instruct",
                input_cost_per_1m=0.10,
                output_cost_per_1m=0.10,
                context_window=32768,
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
        """Call Cloudflare Workers AI API"""
        if not self.is_configured():
            raise ValueError(
                "Cloudflare API key not configured. "
                "Set CLOUDFLARE_API_KEY environment variable."
            )

        try:
            import requests
        except ImportError:
            raise ImportError("requests package required. Install with: pip install requests")

        # Cloudflare Workers AI endpoint
        account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        if not account_id:
            raise ValueError("CLOUDFLARE_ACCOUNT_ID environment variable required")

        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()

        data = response.json()
        result = data.get("result", {})
        content = result.get("response", "")

        return ProviderResponse(
            content=content,
            model=model,
            input_tokens=0,  # Cloudflare doesn't return token counts
            output_tokens=0,
            total_tokens=0,
            finish_reason="stop",
            raw_response=data
        )

    def get_available_models(self) -> List[Model]:
        """Get list of available Cloudflare models"""
        return [
            Model(
                name="@cf/qwen/qwen2.5-coder-32b-instruct",
                display_name="Qwen 2.5 Coder 32B",
                context_window=32768,
                description="Code-specialized model on Cloudflare Workers AI",
                supports_vision=False
            ),
        ]
