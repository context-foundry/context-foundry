"""
Configuration management for tool helpers.

This module handles loading configuration from environment variables,
validating configuration, and providing easy access to settings.
"""

import os
from typing import Dict, Any, Optional
from .limits import ToolLimits, get_default_limits, format_limits_summary


class ToolHelpersConfig:
    """Central configuration for tool helpers.

    This class manages all configuration for tool helpers, including:
    - Limits for operations
    - Path handling preferences
    - Token counting settings
    - Truncation behavior

    Configuration can be overridden via environment variables (see ToolLimits).
    """

    def __init__(self, limits: Optional[ToolLimits] = None):
        """Initialize configuration.

        Args:
            limits: Custom ToolLimits instance (uses defaults if None)
        """
        self.limits = limits if limits is not None else get_default_limits()
        self._debug = os.environ.get('CF_DEBUG', '').lower() in ('true', '1', 'yes')

    @property
    def debug(self) -> bool:
        """Whether debug mode is enabled."""
        return self._debug

    def get_limit(self, operation_type: str, key: str, default: Any = None) -> Any:
        """Get a specific limit value.

        Args:
            operation_type: Operation type (e.g., 'file_read', 'grep')
            key: Limit key (e.g., 'max_chars', 'timeout_seconds')
            default: Default value if limit not found

        Returns:
            Limit value or default

        Example:
            >>> config = ToolHelpersConfig()
            >>> config.get_limit('file_read', 'max_chars')
            500000
        """
        from .limits import get_limit_for_operation
        op_limits = get_limit_for_operation(operation_type, self.limits)
        return op_limits.get(key, default)

    def format_config_summary(self) -> str:
        """Format configuration as human-readable summary.

        Returns:
            Formatted configuration string
        """
        lines = ["Tool Helpers Configuration:"]
        lines.append(f"  Debug Mode: {'enabled' if self.debug else 'disabled'}")
        lines.append("")
        lines.append(format_limits_summary(self.limits))

        return '\n'.join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation of configuration
        """
        from dataclasses import asdict
        return {
            'debug': self.debug,
            'limits': asdict(self.limits)
        }

    @classmethod
    def from_env(cls) -> 'ToolHelpersConfig':
        """Create configuration from environment variables.

        Returns:
            ToolHelpersConfig instance with environment overrides

        Example:
            >>> os.environ['CF_LIMIT_FILE_READ_CHARS'] = '100000'
            >>> config = ToolHelpersConfig.from_env()
            >>> config.limits.max_file_read_chars
            100000
        """
        return cls(limits=get_default_limits())


# Global configuration instance (lazy-loaded)
_global_config: Optional[ToolHelpersConfig] = None


def get_config() -> ToolHelpersConfig:
    """Get global configuration instance.

    This function returns a singleton configuration instance that is
    initialized from environment variables on first call.

    Returns:
        Global ToolHelpersConfig instance

    Example:
        >>> config = get_config()
        >>> config.limits.max_file_read_chars
        500000
    """
    global _global_config
    if _global_config is None:
        _global_config = ToolHelpersConfig.from_env()
    return _global_config


def reset_config():
    """Reset global configuration (useful for testing).

    Example:
        >>> reset_config()
        >>> config = get_config()  # Fresh configuration
    """
    global _global_config
    _global_config = None


def print_config():
    """Print current configuration to stdout.

    Useful for debugging and verifying configuration.
    """
    config = get_config()
    print(config.format_config_summary())


if __name__ == '__main__':
    # When run as script, print configuration
    print_config()
