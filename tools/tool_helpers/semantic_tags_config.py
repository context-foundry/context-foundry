"""
Configuration for semantic tagging system.

Provides environment variable-based configuration for semantic tags,
following the same pattern as limits.py.
"""

from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class SemanticTagsConfig:
    """
    Configuration for semantic tagging system.
    
    All settings can be overridden via environment variables (CF_SEMANTIC_TAGS_*).
    """
    
    # Global enable/disable
    enabled: bool = True
    
    # Tag type toggles
    enable_file_tags: bool = True       # dir/file/link tags
    enable_match_tags: bool = True      # match:def/call/import tags
    enable_category_tags: bool = True   # source/test/config tags
    
    # Verbosity level
    verbosity: str = 'normal'  # 'minimal', 'normal', or 'detailed'
    
    # Include optional metadata
    include_file_sizes: bool = True     # Show file sizes in listings
    include_line_counts: bool = True    # Show line counts in glob results
    include_file_types: bool = True     # Show file type hints (e.g., python)
    
    # Performance limits
    max_dir_scan_items: int = 1000      # Max items to count in directory
    max_line_count_bytes: int = 1000000 # Max file size for line counting (1MB)
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.verbosity not in ('minimal', 'normal', 'detailed'):
            raise ValueError(
                f"verbosity must be 'minimal', 'normal', or 'detailed', got '{self.verbosity}'"
            )
        
        if self.max_dir_scan_items <= 0:
            raise ValueError(
                f"max_dir_scan_items must be positive, got {self.max_dir_scan_items}"
            )
        
        if self.max_line_count_bytes <= 0:
            raise ValueError(
                f"max_line_count_bytes must be positive, got {self.max_line_count_bytes}"
            )


def get_default_config() -> SemanticTagsConfig:
    """
    Get default configuration with environment variable overrides.
    
    Environment variables:
    - CF_SEMANTIC_TAGS_ENABLED: "true" or "false" (default: true)
    - CF_ENABLE_FILE_TAGS: "true" or "false" (default: true)
    - CF_ENABLE_MATCH_TAGS: "true" or "false" (default: true)
    - CF_ENABLE_CATEGORY_TAGS: "true" or "false" (default: true)
    - CF_SEMANTIC_TAGS_VERBOSITY: "minimal", "normal", or "detailed" (default: normal)
    - CF_INCLUDE_FILE_SIZES: "true" or "false" (default: true)
    - CF_INCLUDE_LINE_COUNTS: "true" or "false" (default: true)
    - CF_INCLUDE_FILE_TYPES: "true" or "false" (default: true)
    - CF_MAX_DIR_SCAN_ITEMS: integer (default: 1000)
    - CF_MAX_LINE_COUNT_BYTES: integer (default: 1000000)
    
    Returns:
        SemanticTagsConfig instance with defaults or environment overrides
    
    Example:
        >>> config = get_default_config()
        >>> config.enabled
        True
        
        >>> os.environ['CF_SEMANTIC_TAGS_ENABLED'] = 'false'
        >>> config = get_default_config()
        >>> config.enabled
        False
    """
    def get_bool_env(key: str, default: bool) -> bool:
        """Get boolean from environment or use default."""
        value = os.environ.get(key)
        if value is None:
            return default
        return value.lower() in ('true', '1', 'yes', 'on')
    
    def get_int_env(key: str, default: int) -> int:
        """Get integer from environment or use default."""
        value = os.environ.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            print(f"Warning: Invalid {key}={value}, using default {default}")
            return default
    
    def get_str_env(key: str, default: str) -> str:
        """Get string from environment or use default."""
        return os.environ.get(key, default)
    
    return SemanticTagsConfig(
        enabled=get_bool_env('CF_SEMANTIC_TAGS_ENABLED', True),
        enable_file_tags=get_bool_env('CF_ENABLE_FILE_TAGS', True),
        enable_match_tags=get_bool_env('CF_ENABLE_MATCH_TAGS', True),
        enable_category_tags=get_bool_env('CF_ENABLE_CATEGORY_TAGS', True),
        verbosity=get_str_env('CF_SEMANTIC_TAGS_VERBOSITY', 'normal'),
        include_file_sizes=get_bool_env('CF_INCLUDE_FILE_SIZES', True),
        include_line_counts=get_bool_env('CF_INCLUDE_LINE_COUNTS', True),
        include_file_types=get_bool_env('CF_INCLUDE_FILE_TYPES', True),
        max_dir_scan_items=get_int_env('CF_MAX_DIR_SCAN_ITEMS', 1000),
        max_line_count_bytes=get_int_env('CF_MAX_LINE_COUNT_BYTES', 1000000),
    )


# Singleton cache for default config (avoids repeated environment variable reads)
_config_cache: Optional[SemanticTagsConfig] = None


def get_cached_config() -> SemanticTagsConfig:
    """
    Get cached default config (reads environment variables only once).
    
    Returns:
        Cached SemanticTagsConfig instance
    
    Example:
        >>> config1 = get_cached_config()
        >>> config2 = get_cached_config()
        >>> config1 is config2
        True
    """
    global _config_cache
    if _config_cache is None:
        _config_cache = get_default_config()
    return _config_cache


def reset_config_cache():
    """
    Reset the configuration cache.
    
    Useful for testing or when environment variables change.
    """
    global _config_cache
    _config_cache = None
