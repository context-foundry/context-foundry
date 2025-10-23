#!/usr/bin/env python3
"""
Unified AI Client
Routes API calls to appropriate providers based on phase configuration
"""

import os
import json
import hashlib
import time
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from pathlib import Path
from ace.provider_registry import get_registry
from ace.providers.base_provider import ProviderResponse
from ace.cost_tracker import CostTracker
from ace.model_router import ModelRouter


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

    Features:
    - Response caching for identical prompts (50-70% cost savings on repeated queries)
    - Configurable cache TTL (default: 7 days)
    - Automatic cache invalidation
    """

    def __init__(
        self,
        config: Optional[PhaseConfig] = None,
        log_dir: Optional[Path] = None,
        session_id: Optional[str] = None,
        cost_tracker: Optional[CostTracker] = None,
        enable_cache: bool = True,
        cache_ttl_hours: int = 168,  # 7 days default
        model_router: Optional[ModelRouter] = None,
        enable_routing: bool = True
    ):
        """
        Initialize AI client.

        Args:
            config: Phase configuration (loads from env if None)
            log_dir: Directory for logs
            session_id: Session identifier
            cost_tracker: Cost tracker instance (creates new if None)
            enable_cache: Enable response caching (default: True)
            cache_ttl_hours: Cache time-to-live in hours (default: 168 = 7 days)
            model_router: ModelRouter instance (creates new if None)
            enable_routing: Enable intelligent model routing (default: True)
        """
        self.registry = get_registry()
        self.config = config or self._load_config_from_env()
        self.log_dir = log_dir
        self.session_id = session_id
        self.cost_tracker = cost_tracker or CostTracker()
        self.enable_cache = enable_cache
        self.cache_ttl_hours = cache_ttl_hours
        self.model_router = model_router or (ModelRouter() if enable_routing else None)

        # Setup cache directory
        self.cache_dir = Path.home() / ".context-foundry" / "cache" / "llm_responses"
        if self.enable_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Validate configuration
        self._validate_config()

        # Track conversation history per phase
        self.scout_history: List[Dict[str, str]] = []
        self.architect_history: List[Dict[str, str]] = []
        self.builder_history: List[Dict[str, str]] = []

        # Track token usage
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Track cache stats
        self.cache_hits = 0
        self.cache_misses = 0

    def _load_config_from_env(self) -> PhaseConfig:
        """Load phase configuration from environment variables"""

        # Get provider/model for each phase
        # Default to Sonnet 4.5 (latest model with best performance-to-cost)
        scout_provider = os.getenv('SCOUT_PROVIDER', 'anthropic')
        scout_model = os.getenv('SCOUT_MODEL', 'claude-sonnet-4-5-20250929')

        architect_provider = os.getenv('ARCHITECT_PROVIDER', 'anthropic')
        architect_model = os.getenv('ARCHITECT_MODEL', 'claude-sonnet-4-5-20250929')

        builder_provider = os.getenv('BUILDER_PROVIDER', 'anthropic')
        builder_model = os.getenv('BUILDER_MODEL', 'claude-sonnet-4-5-20250929')

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

    def scout(self, prompt: str, task: Optional[Any] = None, **kwargs) -> ProviderResponse:
        """
        Call Scout phase with configured provider/model.

        Args:
            prompt: User prompt
            task: Optional task object for routing decisions
            **kwargs: Additional provider-specific parameters

        Returns:
            ProviderResponse
        """
        return self._call_phase('scout', prompt, self.scout_history, task=task, **kwargs)

    def architect(self, prompt: str, task: Optional[Any] = None, workflow_complexity: Optional[str] = None, **kwargs) -> ProviderResponse:
        """
        Call Architect phase with configured provider/model.

        Args:
            prompt: User prompt
            task: Optional task object for routing decisions
            workflow_complexity: Optional workflow complexity assessment
            **kwargs: Additional provider-specific parameters

        Returns:
            ProviderResponse
        """
        return self._call_phase('architect', prompt, self.architect_history, task=task, workflow_complexity=workflow_complexity, **kwargs)

    def builder(self, prompt: str, task: Optional[Any] = None, task_num: Optional[int] = None, **kwargs) -> ProviderResponse:
        """
        Call Builder phase with configured provider/model.
        Supports per-task overrides and intelligent routing.

        Args:
            prompt: User prompt
            task: Optional task object for routing decisions
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
                    task=task,
                    **kwargs
                )

        # Use default builder configuration with routing
        return self._call_phase('builder', prompt, self.builder_history, task=task, **kwargs)

    def _call_phase(
        self,
        phase_name: str,
        prompt: str,
        history: List[Dict[str, str]],
        task: Optional[Any] = None,
        workflow_complexity: Optional[str] = None,
        **kwargs
    ) -> ProviderResponse:
        """
        Call API for a specific phase.

        Args:
            phase_name: Phase name ('scout', 'architect', 'builder')
            prompt: User prompt
            history: Conversation history for this phase
            task: Optional task object for routing
            workflow_complexity: Optional workflow complexity
            **kwargs: Additional parameters

        Returns:
            ProviderResponse
        """
        config = getattr(self.config, phase_name)
        return self._call_with_config(
            config, prompt, history, phase_name,
            task=task, workflow_complexity=workflow_complexity, **kwargs
        )

    def _get_cache_key(self, prompt: str, model: str, history: List[Dict[str, str]]) -> str:
        """
        Generate cache key from prompt, model, and conversation history.

        Args:
            prompt: User prompt
            model: Model name
            history: Conversation history

        Returns:
            SHA256 hash as cache key
        """
        # Include prompt, model, and history in cache key
        # This ensures different contexts get different cache entries
        cache_content = {
            'model': model,
            'prompt': prompt,
            'history': history[:-1] if history else []  # Exclude current prompt from history
        }
        content_str = json.dumps(cache_content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[ProviderResponse]:
        """
        Retrieve response from cache if valid.

        Args:
            cache_key: Cache key

        Returns:
            Cached ProviderResponse if found and valid, None otherwise
        """
        if not self.enable_cache:
            return None

        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)

            # Check if cache is still valid
            cached_time = cache_data.get('timestamp', 0)
            age_hours = (time.time() - cached_time) / 3600

            if age_hours > self.cache_ttl_hours:
                # Cache expired, delete it
                cache_file.unlink()
                return None

            # Reconstruct ProviderResponse
            response = ProviderResponse(
                content=cache_data['content'],
                input_tokens=cache_data['input_tokens'],
                output_tokens=cache_data['output_tokens'],
                model=cache_data['model']
            )

            self.cache_hits += 1
            return response

        except Exception as e:
            # If cache read fails, ignore and proceed with API call
            print(f"   ⚠️  Cache read error: {e}")
            return None

    def _save_to_cache(self, cache_key: str, response: ProviderResponse, model: str):
        """
        Save response to cache.

        Args:
            cache_key: Cache key
            response: Provider response to cache
            model: Model name
        """
        if not self.enable_cache:
            return

        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            cache_data = {
                'content': response.content,
                'input_tokens': response.input_tokens,
                'output_tokens': response.output_tokens,
                'model': model,
                'timestamp': time.time()
            }

            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)

        except Exception as e:
            # If cache write fails, just log and continue
            print(f"   ⚠️  Cache write error: {e}")

    def _call_with_config(
        self,
        config: ModelConfig,
        prompt: str,
        history: List[Dict[str, str]],
        phase_name: Optional[str] = None,
        task: Optional[Any] = None,
        workflow_complexity: Optional[str] = None,
        **kwargs
    ) -> ProviderResponse:
        """
        Call API with specific configuration, using cache and intelligent routing when possible.

        Args:
            config: Model configuration
            prompt: User prompt
            history: Conversation history
            phase_name: Optional phase name for cost tracking
            task: Optional task object for routing
            workflow_complexity: Optional workflow complexity
            **kwargs: Additional parameters

        Returns:
            ProviderResponse
        """
        # Apply intelligent model routing if enabled
        original_model = config.model
        if self.model_router and phase_name:
            routing_decision = self.model_router.get_model_for_task(
                phase=phase_name,
                task=task,
                workflow_complexity=workflow_complexity,
                context=kwargs.get('routing_context')
            )

            # Override model if router suggests different one
            if routing_decision.model != config.model:
                print(f"   🔀 Model routing: {config.model} → {routing_decision.model}")
                print(f"      Reason: {routing_decision.reason}")
                config = ModelConfig(config.provider, routing_decision.model)

        # Add user message to history first
        history.append({'role': 'user', 'content': prompt})

        # Generate cache key
        cache_key = self._get_cache_key(prompt, config.model, history)

        # Try to get from cache
        cached_response = self._get_from_cache(cache_key)

        if cached_response:
            # Cache hit! Use cached response
            print(f"   💾 Cache hit ({cache_key[:8]}...) - saving ~{cached_response.input_tokens + cached_response.output_tokens} tokens")
            response = cached_response

            # Add cached assistant response to history
            history.append({'role': 'assistant', 'content': response.content})

            # Still track usage for metrics (but no actual API cost)
            self.total_input_tokens += response.input_tokens
            self.total_output_tokens += response.output_tokens

            return response

        # Cache miss - call API
        self.cache_misses += 1

        # Get provider
        provider = self.registry.get(config.provider)

        # Call API
        response = provider.call_api(
            messages=history,
            model=config.model,
            **kwargs
        )

        # Save to cache
        self._save_to_cache(cache_key, response, config.model)

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
            'total_tokens': self.total_input_tokens + self.total_output_tokens,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': f"{(self.cache_hits / (self.cache_hits + self.cache_misses) * 100):.1f}%" if (self.cache_hits + self.cache_misses) > 0 else "0%"
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
        lines.append(f"Cache:     {'Enabled' if self.enable_cache else 'Disabled'} (TTL: {self.cache_ttl_hours}h)")
        if self.cache_hits + self.cache_misses > 0:
            hit_rate = (self.cache_hits / (self.cache_hits + self.cache_misses) * 100)
            lines.append(f"Cache Stats: {self.cache_hits} hits, {self.cache_misses} misses ({hit_rate:.1f}% hit rate)")

        # Add model routing stats if enabled
        if self.model_router:
            lines.append(f"\nModel Routing: Enabled")
            stats = self.model_router.get_routing_stats()
            if stats['total_decisions'] > 0:
                lines.append(f"  Default ({self.model_router.default_model}): {stats['default_model_count']} tasks ({stats['default_model_percentage']:.1f}%)")
                lines.append(f"  Complex ({self.model_router.complex_model}): {stats['complex_model_count']} tasks ({stats['complex_model_percentage']:.1f}%)")
        else:
            lines.append(f"\nModel Routing: Disabled")

        return "\n".join(lines)

    def clear_cache(self, max_age_hours: Optional[int] = None):
        """
        Clear cached responses.

        Args:
            max_age_hours: Only clear cache older than this many hours.
                          If None, clears all cache.
        """
        if not self.cache_dir.exists():
            return

        cleared = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                if max_age_hours is not None:
                    # Only delete if older than max_age_hours
                    with open(cache_file, 'r') as f:
                        cache_data = json.load(f)
                    cached_time = cache_data.get('timestamp', 0)
                    age_hours = (time.time() - cached_time) / 3600

                    if age_hours < max_age_hours:
                        continue  # Keep this one

                cache_file.unlink()
                cleared += 1
            except Exception:
                pass  # Ignore errors, just skip the file

        print(f"✅ Cleared {cleared} cached responses")

    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        total_files = len(list(self.cache_dir.glob("*.json"))) if self.cache_dir.exists() else 0
        total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.json")) if self.cache_dir.exists() else 0

        return {
            'enabled': self.enable_cache,
            'ttl_hours': self.cache_ttl_hours,
            'cache_dir': str(self.cache_dir),
            'cached_responses': total_files,
            'cache_size_mb': total_size / (1024 * 1024),
            'session_hits': self.cache_hits,
            'session_misses': self.cache_misses,
            'session_hit_rate': f"{(self.cache_hits / (self.cache_hits + self.cache_misses) * 100):.1f}%" if (self.cache_hits + self.cache_misses) > 0 else "0%"
        }
