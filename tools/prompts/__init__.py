"""
Prompt Management Tools
Includes cached prompt builder and configuration
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class CacheConfig:
    """Configuration manager for prompt caching"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize cache configuration.

        Args:
            config_path: Path to cache_config.json (default: tools/prompts/cache_config.json)
        """
        if config_path is None:
            # Default to config in same directory
            config_path = Path(__file__).parent / 'cache_config.json'

        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # Return default configuration
            return {
                'version': '1.0.0',
                'caching': {
                    'enabled': True,
                    'ttl': '5m',
                    'min_tokens': 1024,
                    'cache_boundary_line': 1650,
                    'models_supported': [
                        'claude-sonnet-4',
                        'claude-sonnet-3-5',
                        'claude-opus-4',
                        'claude-haiku-3-5'
                    ]
                },
                'metrics': {
                    'track_cache_hits': True,
                    'track_token_savings': True,
                    'track_cost_savings': True
                }
            }

    def is_caching_enabled(self) -> bool:
        """Check if caching is enabled"""
        return self.config['caching'].get('enabled', True)

    def get_cache_ttl(self) -> str:
        """Get cache TTL (5m or 1h)"""
        extended_enabled = self.config['caching'].get('extended_ttl_enabled', False)

        if extended_enabled:
            return self.config['caching'].get('extended_ttl_duration', '1h')
        else:
            return self.config['caching'].get('ttl', '5m')

    def get_min_tokens(self) -> int:
        """Get minimum tokens required for caching"""
        return self.config['caching'].get('min_tokens', 1024)

    def get_cache_boundary_line(self) -> int:
        """Get recommended cache boundary line number"""
        return self.config['caching'].get('cache_boundary_line', 1650)

    def is_model_supported(self, model: str) -> bool:
        """
        Check if model supports caching.

        Args:
            model: Model name (e.g., "claude-sonnet-4-20250514")

        Returns:
            True if model supports caching
        """
        supported = self.config['caching'].get('models_supported', [])

        # Check if any supported model name is in the full model string
        return any(m in model for m in supported)

    def should_track_cache_hits(self) -> bool:
        """Check if cache hit tracking is enabled"""
        return self.config['metrics'].get('track_cache_hits', True)

    def should_track_token_savings(self) -> bool:
        """Check if token savings tracking is enabled"""
        return self.config['metrics'].get('track_token_savings', True)

    def should_track_cost_savings(self) -> bool:
        """Check if cost savings tracking is enabled"""
        return self.config['metrics'].get('track_cost_savings', True)

    def get_fallback_behavior(self) -> str:
        """Get fallback behavior on error"""
        return self.config.get('fallback', {}).get('on_error', 'disable_caching')

    def should_warn_on_small_section(self) -> bool:
        """Check if warnings should be shown for small cacheable sections"""
        return self.config.get('fallback', {}).get('warn_on_small_section', True)

    def reload(self):
        """Reload configuration from file"""
        self.config = self._load_config()

    def save(self):
        """Save current configuration to file"""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def enable_caching(self):
        """Enable prompt caching"""
        self.config['caching']['enabled'] = True
        self.save()

    def disable_caching(self):
        """Disable prompt caching"""
        self.config['caching']['enabled'] = False
        self.save()

    def set_cache_ttl(self, ttl: str):
        """
        Set cache TTL.

        Args:
            ttl: "5m" for 5 minutes or "1h" for 1 hour
        """
        if ttl not in ['5m', '1h']:
            raise ValueError(f"Invalid TTL: {ttl}. Must be '5m' or '1h'")

        if ttl == '1h':
            self.config['caching']['extended_ttl_enabled'] = True
            self.config['caching']['extended_ttl_duration'] = '1h'
        else:
            self.config['caching']['extended_ttl_enabled'] = False
            self.config['caching']['ttl'] = '5m'

        self.save()

    def __repr__(self) -> str:
        """String representation"""
        return f"CacheConfig(enabled={self.is_caching_enabled()}, ttl={self.get_cache_ttl()})"


# Export main classes
__all__ = ['CacheConfig']
