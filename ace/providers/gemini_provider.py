#!/usr/bin/env python3
"""
Google Gemini Provider
"""

import os
from typing import List, Dict, Optional
from datetime import datetime
from ace.providers.base_provider import (
    BaseProvider, Model, ModelPricing, ProviderResponse
)


class GeminiProvider(BaseProvider):
    """Google Gemini provider"""

    def _get_provider_name(self) -> str:
        return "gemini"

    def _get_api_key(self) -> Optional[str]:
        return os.getenv("GOOGLE_API_KEY", "").strip() or None

    def get_pricing_url(self) -> str:
        return "https://ai.google.dev/gemini-api/docs/pricing"

    def fetch_pricing(self) -> Dict[str, ModelPricing]:
        """Fetch Gemini pricing"""
        return self._get_fallback_pricing()

    def _get_fallback_pricing(self) -> Dict[str, ModelPricing]:
        """
        Fallback pricing for Gemini models.
        Based on: https://ai.google.dev/gemini-api/docs/pricing
        """
        now = datetime.now()

        return {
            "gemini-2.0-flash-exp": ModelPricing(
                model="gemini-2.0-flash-exp",
                input_cost_per_1m=0.075,
                output_cost_per_1m=0.30,
                context_window=1000000,
                updated_at=now
            ),
            "gemini-1.5-pro": ModelPricing(
                model="gemini-1.5-pro",
                input_cost_per_1m=1.25,
                output_cost_per_1m=5.00,
                context_window=2000000,
                updated_at=now
            ),
            "gemini-1.5-flash": ModelPricing(
                model="gemini-1.5-flash",
                input_cost_per_1m=0.075,
                output_cost_per_1m=0.30,
                context_window=1000000,
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
        """Call Gemini API"""
        if not self.is_configured():
            raise ValueError(
                "Google API key not configured. "
                "Set GOOGLE_API_KEY environment variable."
            )

        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai package required. "
                "Install with: pip install google-generativeai"
            )

        genai.configure(api_key=self.api_key)

        # Convert messages to Gemini format
        contents = []
        for msg in messages:
            if msg['role'] != 'system':  # Gemini doesn't have system role
                contents.append({
                    'role': 'user' if msg['role'] == 'user' else 'model',
                    'parts': [msg['content']]
                })

        # Call API
        gemini_model = genai.GenerativeModel(model)
        response = gemini_model.generate_content(
            contents,
            generation_config=genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature
            )
        )

        return ProviderResponse(
            content=response.text,
            model=model,
            input_tokens=response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
            output_tokens=response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
            total_tokens=response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
            finish_reason='stop',
            raw_response=response
        )

    def get_available_models(self) -> List[Model]:
        """Get list of available Gemini models"""
        return [
            Model(
                name="gemini-2.0-flash-exp",
                display_name="Gemini 2.0 Flash (Experimental)",
                context_window=1000000,
                description="Next-gen multimodal model, very fast and affordable",
                supports_vision=True
            ),
            Model(
                name="gemini-1.5-pro",
                display_name="Gemini 1.5 Pro",
                context_window=2000000,
                description="Most capable, 2M context window",
                supports_vision=True
            ),
            Model(
                name="gemini-1.5-flash",
                display_name="Gemini 1.5 Flash",
                context_window=1000000,
                description="Fast and versatile for scaled tasks",
                supports_vision=True
            ),
        ]
