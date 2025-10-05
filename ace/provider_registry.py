#!/usr/bin/env python3
"""
Provider Registry
Manages all available AI providers
"""

from typing import Dict, List, Optional
from ace.providers.base_provider import BaseProvider, Model


class ProviderRegistry:
    """Central registry of all AI providers"""

    def __init__(self):
        self.providers: Dict[str, BaseProvider] = {}
        self._register_providers()

    def _register_providers(self):
        """Register all available providers"""
        # Import providers here to avoid circular imports
        # We'll add these as we implement them

        try:
            from ace.providers.anthropic_provider import AnthropicProvider
            self.providers['anthropic'] = AnthropicProvider()
        except ImportError:
            pass  # Not implemented yet

        try:
            from ace.providers.openai_provider import OpenAIProvider
            self.providers['openai'] = OpenAIProvider()
        except ImportError:
            pass

        try:
            from ace.providers.gemini_provider import GeminiProvider
            self.providers['gemini'] = GeminiProvider()
        except ImportError:
            pass

        try:
            from ace.providers.groq_provider import GroqProvider
            self.providers['groq'] = GroqProvider()
        except ImportError:
            pass

        try:
            from ace.providers.cloudflare_provider import CloudflareProvider
            self.providers['cloudflare'] = CloudflareProvider()
        except ImportError:
            pass

        try:
            from ace.providers.fireworks_provider import FireworksProvider
            self.providers['fireworks'] = FireworksProvider()
        except ImportError:
            pass

        try:
            from ace.providers.mistral_provider import MistralProvider
            self.providers['mistral'] = MistralProvider()
        except ImportError:
            pass

    def get(self, name: str) -> BaseProvider:
        """
        Get provider by name.

        Args:
            name: Provider name (e.g., 'anthropic', 'openai')

        Returns:
            Provider instance

        Raises:
            ValueError: If provider not found
        """
        if name not in self.providers:
            available = ', '.join(self.providers.keys())
            raise ValueError(
                f"Provider '{name}' not found. Available: {available}"
            )
        return self.providers[name]

    def list_providers(self) -> List[str]:
        """Get list of available provider names"""
        return list(self.providers.keys())

    def list_all_models(self) -> Dict[str, List[Model]]:
        """
        Get all models from all providers.

        Returns:
            Dict mapping provider name to list of models
        """
        all_models = {}
        for name, provider in self.providers.items():
            try:
                all_models[name] = provider.get_available_models()
            except Exception as e:
                print(f"Warning: Failed to get models for {name}: {e}")
                all_models[name] = []
        return all_models

    def get_configured_providers(self) -> List[str]:
        """Get list of providers that have API keys configured"""
        return [
            name for name, provider in self.providers.items()
            if provider.is_configured()
        ]

    def validate_config(self, provider: str, model: str) -> tuple[bool, Optional[str]]:
        """
        Validate provider and model configuration.

        Returns:
            (is_valid, error_message)
        """
        # Check if provider exists
        if provider not in self.providers:
            return False, f"Provider '{provider}' not found"

        # Check if provider is configured
        provider_obj = self.providers[provider]
        if not provider_obj.is_configured():
            return False, f"Provider '{provider}' not configured (missing API key)"

        # Check if model is valid
        if not provider_obj.validate_model(model):
            available = [m.name for m in provider_obj.get_available_models()]
            return False, f"Model '{model}' not available for {provider}. Available: {', '.join(available)}"

        return True, None


# Global registry instance
_registry = None


def get_registry() -> ProviderRegistry:
    """Get global provider registry instance"""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry
