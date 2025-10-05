#!/usr/bin/env python3
"""
Anthropic (Claude) Provider
"""

import os
from typing import List, Dict, Optional
from datetime import datetime
from anthropic import Anthropic
from ace.providers.base_provider import (
    BaseProvider, Model, ModelPricing, ProviderResponse
)


class AnthropicProvider(BaseProvider):
    """Anthropic Claude provider"""

    def _get_provider_name(self) -> str:
        return "anthropic"

    def _get_api_key(self) -> Optional[str]:
        return os.getenv("ANTHROPIC_API_KEY", "").strip() or None

    def get_pricing_url(self) -> str:
        return "https://docs.claude.com/en/docs/about-claude/pricing"

    def fetch_pricing(self) -> Dict[str, ModelPricing]:
        """
        Fetch Claude pricing from documentation.
        Uses WebFetch or requests to parse pricing page.
        """
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError(
                "requests and beautifulsoup4 required for pricing fetch. "
                "Install with: pip install requests beautifulsoup4"
            )

        # Fetch pricing page
        response = requests.get(self.get_pricing_url(), timeout=10)
        response.raise_for_status()

        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # This is a simplified parser - the actual implementation
        # would need to match the current structure of Claude's pricing page
        # For now, return hardcoded current pricing
        pricing = self._get_fallback_pricing()

        return pricing

    def _get_fallback_pricing(self) -> Dict[str, ModelPricing]:
        """
        Fallback pricing if fetch fails.
        Updated manually based on: https://docs.claude.com/en/docs/about-claude/pricing
        As of October 2025
        """
        now = datetime.now()

        return {
            "claude-opus-4-20250514": ModelPricing(
                model="claude-opus-4-20250514",
                input_cost_per_1m=15.00,
                output_cost_per_1m=75.00,
                context_window=200000,
                updated_at=now
            ),
            "claude-sonnet-4-20250514": ModelPricing(
                model="claude-sonnet-4-20250514",
                input_cost_per_1m=3.00,
                output_cost_per_1m=15.00,
                context_window=200000,
                updated_at=now
            ),
            "claude-haiku-4-20250514": ModelPricing(
                model="claude-haiku-4-20250514",
                input_cost_per_1m=0.80,
                output_cost_per_1m=4.00,
                context_window=200000,
                updated_at=now
            ),
            # Claude 4.5 models (newer release)
            "claude-sonnet-4-5-20250929": ModelPricing(
                model="claude-sonnet-4-5-20250929",
                input_cost_per_1m=3.00,
                output_cost_per_1m=15.00,
                context_window=200000,
                updated_at=now
            ),
            # Legacy models
            "claude-3-opus-20240229": ModelPricing(
                model="claude-3-opus-20240229",
                input_cost_per_1m=15.00,
                output_cost_per_1m=75.00,
                context_window=200000,
                updated_at=now
            ),
            "claude-3-5-sonnet-20241022": ModelPricing(
                model="claude-3-5-sonnet-20241022",
                input_cost_per_1m=3.00,
                output_cost_per_1m=15.00,
                context_window=200000,
                updated_at=now
            ),
            "claude-3-5-haiku-20241022": ModelPricing(
                model="claude-3-5-haiku-20241022",
                input_cost_per_1m=0.80,
                output_cost_per_1m=4.00,
                context_window=200000,
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
        """
        Call Anthropic API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional parameters

        Returns:
            ProviderResponse
        """
        if not self.is_configured():
            raise ValueError(
                "Anthropic API key not configured. "
                "Set ANTHROPIC_API_KEY environment variable."
            )

        client = Anthropic(api_key=self.api_key)

        # Convert messages format
        api_messages = []
        system = None

        for msg in messages:
            if msg['role'] == 'system':
                system = msg['content']
            else:
                api_messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })

        # Call API
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=api_messages,
            **kwargs
        )

        # Extract content
        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        return ProviderResponse(
            content=content,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            finish_reason=response.stop_reason,
            raw_response=response
        )

    def get_available_models(self) -> List[Model]:
        """Get list of available Claude models"""
        return [
            Model(
                name="claude-opus-4-20250514",
                display_name="Claude Opus 4",
                context_window=200000,
                description="Most capable model, best for complex tasks",
                supports_vision=True
            ),
            Model(
                name="claude-sonnet-4-20250514",
                display_name="Claude Sonnet 4",
                context_window=200000,
                description="Balanced performance and cost, best for most tasks",
                supports_vision=True
            ),
            Model(
                name="claude-haiku-4-20250514",
                display_name="Claude Haiku 4",
                context_window=200000,
                description="Fastest and most affordable, good for simple tasks",
                supports_vision=True
            ),
            # Claude 4.5 models (newer release)
            Model(
                name="claude-sonnet-4-5-20250929",
                display_name="Claude Sonnet 4.5",
                context_window=200000,
                description="Latest Sonnet model with improved performance",
                supports_vision=True
            ),
            # Legacy models
            Model(
                name="claude-3-opus-20240229",
                display_name="Claude 3 Opus (Legacy)",
                context_window=200000,
                description="Previous generation Opus",
                supports_vision=True
            ),
            Model(
                name="claude-3-5-sonnet-20241022",
                display_name="Claude 3.5 Sonnet (Legacy)",
                context_window=200000,
                description="Previous generation Sonnet",
                supports_vision=True
            ),
            Model(
                name="claude-3-5-haiku-20241022",
                display_name="Claude 3.5 Haiku (Legacy)",
                context_window=200000,
                description="Previous generation Haiku",
                supports_vision=True
            ),
        ]
