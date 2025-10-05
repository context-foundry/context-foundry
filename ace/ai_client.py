#!/usr/bin/env python3
"""
Unified AI Client
Routes API calls to appropriate providers based on phase configuration
"""

import os
from typing import Optional, Dict, List
from dataclasses import dataclass
from pathlib import Path
from ace.provider_registry import get_registry
from ace.providers.base_provider import ProviderResponse
from ace.cost_tracker import CostTracker


@dataclass
class ModelConfig:
    """Configuration for a model"""
    provider: str
    model: str


@dataclass
class PhaseConfig:
    """Configuration for all phases"""
    scout: ModelConfig
    architect: ModelConfig
    builder: ModelConfig


class AIClient:
    """
    Unified AI client that routes calls to different providers per phase.
    Gives users complete freedom to use any provider for any phase.
    """

    def __init__(
        self,
        config: Optional[PhaseConfig] = None,
        log_dir: Optional[Path] = None,
        session_id: Optional[str] = None,
        cost_tracker: Optional[CostTracker] = None
    ):
        """
        Initialize AI client.

        Args:
            config: Phase configuration (loads from env if None)
            log_dir: Directory for logs
            session_id: Session identifier
            cost_tracker: Cost tracker instance (creates new if None)
        """
        self.registry = get_registry()
        self.config = config or self._load_config_from_env()
        self.log_dir = log_dir
        self.session_id = session_id
        self.cost_tracker = cost_tracker or CostTracker()

        # Validate configuration
        self._validate_config()

        # Track conversation history per phase
        self.scout_history: List[Dict[str, str]] = []
        self.architect_history: List[Dict[str, str]] = []
        self.builder_history: List[Dict[str, str]] = []

        # Track token usage
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def _load_config_from_env(self) -> PhaseConfig:
        """Load phase configuration from environment variables"""

        # Get provider/model for each phase
        scout_provider = os.getenv('SCOUT_PROVIDER', 'anthropic')
        scout_model = os.getenv('SCOUT_MODEL', 'claude-sonnet-4-20250514')

        architect_provider = os.getenv('ARCHITECT_PROVIDER', 'anthropic')
        architect_model = os.getenv('ARCHITECT_MODEL', 'claude-sonnet-4-20250514')

        builder_provider = os.getenv('BUILDER_PROVIDER', 'anthropic')
        builder_model = os.getenv('BUILDER_MODEL', 'claude-sonnet-4-20250514')

        return PhaseConfig(
            scout=ModelConfig(scout_provider, scout_model),
            architect=ModelConfig(architect_provider, architect_model),
            builder=ModelConfig(builder_provider, builder_model)
        )

    def _validate_config(self):
        """Validate that all providers are configured"""
        for phase_name in ['scout', 'architect', 'builder']:
            config = getattr(self.config, phase_name)

            # Validate provider and model
            is_valid, error = self.registry.validate_config(
                config.provider,
                config.model
            )

            if not is_valid:
                raise ValueError(
                    f"{phase_name.title()} phase configuration error: {error}"
                )

    def scout(self, prompt: str, **kwargs) -> ProviderResponse:
        """
        Call Scout phase with configured provider/model.

        Args:
            prompt: User prompt
            **kwargs: Additional provider-specific parameters

        Returns:
            ProviderResponse
        """
        return self._call_phase('scout', prompt, self.scout_history, **kwargs)

    def architect(self, prompt: str, **kwargs) -> ProviderResponse:
        """
        Call Architect phase with configured provider/model.

        Args:
            prompt: User prompt
            **kwargs: Additional provider-specific parameters

        Returns:
            ProviderResponse
        """
        return self._call_phase('architect', prompt, self.architect_history, **kwargs)

    def builder(self, prompt: str, task_num: Optional[int] = None, **kwargs) -> ProviderResponse:
        """
        Call Builder phase with configured provider/model.
        Supports per-task overrides.

        Args:
            prompt: User prompt
            task_num: Optional task number for per-task overrides
            **kwargs: Additional provider-specific parameters

        Returns:
            ProviderResponse
        """
        # Check for task-specific override
        if task_num:
            override_provider = os.getenv(f'BUILDER_TASK_{task_num}_PROVIDER')
            override_model = os.getenv(f'BUILDER_TASK_{task_num}_MODEL')

            if override_provider and override_model:
                # Use override configuration
                config = ModelConfig(override_provider, override_model)
                return self._call_with_config(
                    config,
                    prompt,
                    self.builder_history,
                    'builder',
                    **kwargs
                )

        # Use default builder configuration
        return self._call_phase('builder', prompt, self.builder_history, **kwargs)

    def _call_phase(
        self,
        phase_name: str,
        prompt: str,
        history: List[Dict[str, str]],
        **kwargs
    ) -> ProviderResponse:
        """
        Call API for a specific phase.

        Args:
            phase_name: Phase name ('scout', 'architect', 'builder')
            prompt: User prompt
            history: Conversation history for this phase
            **kwargs: Additional parameters

        Returns:
            ProviderResponse
        """
        config = getattr(self.config, phase_name)
        return self._call_with_config(config, prompt, history, phase_name, **kwargs)

    def _call_with_config(
        self,
        config: ModelConfig,
        prompt: str,
        history: List[Dict[str, str]],
        phase_name: Optional[str] = None,
        **kwargs
    ) -> ProviderResponse:
        """
        Call API with specific configuration.

        Args:
            config: Model configuration
            prompt: User prompt
            history: Conversation history
            phase_name: Optional phase name for cost tracking
            **kwargs: Additional parameters

        Returns:
            ProviderResponse
        """
        # Get provider
        provider = self.registry.get(config.provider)

        # Add user message to history
        history.append({'role': 'user', 'content': prompt})

        # Call API
        response = provider.call_api(
            messages=history,
            model=config.model,
            **kwargs
        )

        # Add assistant response to history
        history.append({'role': 'assistant', 'content': response.content})

        # Track usage
        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens

        # Track cost
        if phase_name and self.cost_tracker:
            self.cost_tracker.track_usage(
                phase=phase_name,
                provider=config.provider,
                model=config.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens
            )

        # Log if enabled
        if self.log_dir:
            self._log_call(config, prompt, response)

        return response

    def _log_call(self, config: ModelConfig, prompt: str, response: ProviderResponse):
        """Log API call to file"""
        if not self.log_dir:
            return

        log_file = self.log_dir / f"{config.provider}_{config.model}_calls.jsonl"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        import json
        from datetime import datetime

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'provider': config.provider,
            'model': config.model,
            'prompt_length': len(prompt),
            'input_tokens': response.input_tokens,
            'output_tokens': response.output_tokens,
            'total_tokens': response.total_tokens
        }

        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

    def get_usage_stats(self) -> Dict:
        """Get token usage statistics"""
        return {
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_tokens': self.total_input_tokens + self.total_output_tokens
        }

    def get_cost_summary(self, verbose: bool = True) -> str:
        """
        Get formatted cost summary.

        Args:
            verbose: Include detailed breakdown

        Returns:
            Formatted cost summary string
        """
        return self.cost_tracker.format_summary(verbose=verbose)

    def get_total_cost(self) -> float:
        """Get total cost across all phases"""
        return self.cost_tracker.get_total_cost()

    def get_cost_details(self) -> Dict:
        """Get detailed cost breakdown"""
        return self.cost_tracker.get_summary()

    def reset_history(self, phase: Optional[str] = None):
        """
        Reset conversation history.

        Args:
            phase: Specific phase to reset, or None for all
        """
        if phase == 'scout' or phase is None:
            self.scout_history = []
        if phase == 'architect' or phase is None:
            self.architect_history = []
        if phase == 'builder' or phase is None:
            self.builder_history = []

    def get_config_summary(self) -> str:
        """Get human-readable configuration summary"""
        lines = []
        lines.append("AI Configuration")
        lines.append("=" * 60)
        lines.append(f"Scout:     {self.config.scout.provider} / {self.config.scout.model}")
        lines.append(f"Architect: {self.config.architect.provider} / {self.config.architect.model}")
        lines.append(f"Builder:   {self.config.builder.provider} / {self.config.builder.model}")
        return "\n".join(lines)
