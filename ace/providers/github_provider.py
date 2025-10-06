#!/usr/bin/env python3
"""
GitHub Models Provider
Uses GitHub PAT to access GitHub Models API (FREE)
Provides GPT-4o and other models via https://models.inference.ai.azure.com
"""

import os
import requests
import time
import re
from typing import List, Dict, Optional
from datetime import datetime
from ace.providers.base_provider import (
    BaseProvider, Model, ModelPricing, ProviderResponse
)


class GitHubProvider(BaseProvider):
    """GitHub Models provider - FREE access to GPT-4o and other models"""

    def __init__(self):
        super().__init__()

    def _get_provider_name(self) -> str:
        return "github"

    def _get_api_key(self) -> Optional[str]:
        """Get GitHub Personal Access Token"""
        return os.getenv("GITHUB_TOKEN", "").strip() or None

    def get_pricing_url(self) -> str:
        return "https://github.com/marketplace/models"

    def fetch_pricing(self) -> Dict[str, ModelPricing]:
        """
        Fetch GitHub Models pricing.
        GitHub Models is FREE with rate limits.
        """
        return self._get_fallback_pricing()

    def _get_fallback_pricing(self) -> Dict[str, ModelPricing]:
        """
        GitHub Models pricing - FREE.
        Rate limits: 10,000 requests/day, 10M tokens/day per model.
        """
        now = datetime.now()

        return {
            "gpt-4o": ModelPricing(
                model="gpt-4o",
                input_cost_per_1m=0.00,  # FREE
                output_cost_per_1m=0.00,  # FREE
                context_window=128000,
                updated_at=now
            ),
            "gpt-4": ModelPricing(
                model="gpt-4",
                input_cost_per_1m=0.00,  # FREE
                output_cost_per_1m=0.00,  # FREE
                context_window=8192,
                updated_at=now
            ),
            "gpt-3.5-turbo": ModelPricing(
                model="gpt-3.5-turbo",
                input_cost_per_1m=0.00,  # FREE
                output_cost_per_1m=0.00,  # FREE
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
        """Call GitHub Models API (FREE)"""
        if not self.is_configured():
            raise ValueError(
                "GitHub token not configured. "
                "Set GITHUB_TOKEN environment variable. "
                "Generate at: https://github.com/settings/tokens"
            )

        # Use PAT directly with GitHub Models API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs
        }

        # Retry logic for rate limits (429 errors)
        max_retries = 3
        base_wait_time = 60  # seconds

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    "https://models.inference.ai.azure.com/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120
                )

                # Handle rate limit (429)
                if response.status_code == 429:
                    if attempt < max_retries - 1:  # Don't retry on last attempt
                        # Parse wait time from error message
                        try:
                            error_data = response.json()
                            error_msg = error_data.get('error', {}).get('message', '')

                            # Try to extract wait time from message like "wait 60 seconds"
                            wait_match = re.search(r'wait (\d+) seconds?', error_msg, re.IGNORECASE)
                            if wait_match:
                                base_wait_time = int(wait_match.group(1))
                        except:
                            pass  # Use default wait time

                        # Exponential backoff: 60s, 90s, 120s
                        wait_time = base_wait_time * (1.5 ** attempt)
                        print(f"\n⏳ Rate limit hit. Waiting {wait_time:.0f}s before retry (attempt {attempt+1}/{max_retries})...")
                        time.sleep(wait_time)
                        continue  # Retry
                    else:
                        # Last attempt failed
                        raise ValueError(
                            f"GitHub Models API error: HTTP {response.status_code}. "
                            f"Response: {response.text}"
                        )

                # Handle other non-200 status codes
                if response.status_code != 200:
                    raise ValueError(
                        f"GitHub Models API error: HTTP {response.status_code}. "
                        f"Response: {response.text}"
                    )

                # Success! Parse response
                data = response.json()

                # Parse OpenAI-compatible response
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

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    # Network error, retry with backoff
                    wait_time = base_wait_time * (1.5 ** attempt)
                    print(f"\n⚠️  Network error. Retrying in {wait_time:.0f}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise ValueError(f"Failed to call GitHub Models API: {e}")

    def get_available_models(self) -> List[Model]:
        """Get list of available GitHub Models (FREE)"""
        return [
            Model(
                name="gpt-4o",
                display_name="GPT-4o",
                context_window=128000,
                description="Best quality GPT-4 model. FREE (10K req/day, 10M tokens/day).",
                supports_vision=True,
                supports_streaming=True
            ),
            Model(
                name="gpt-4",
                display_name="GPT-4",
                context_window=8192,
                description="Original GPT-4. FREE (10K req/day, 10M tokens/day).",
                supports_vision=False,
                supports_streaming=True
            ),
            Model(
                name="gpt-3.5-turbo",
                display_name="GPT-3.5 Turbo",
                context_window=16385,
                description="Faster model. FREE (10K req/day, 10M tokens/day).",
                supports_vision=False,
                supports_streaming=True
            ),
        ]
