"""
Tool Helpers - Utilities for improving agent-tool interactions.

This module provides utilities for:
- Smart truncation with recovery instructions
- Relative path conversion (20-30% token savings)
- Limits enforcement and configuration
- Standardized tool response formatting

Usage:
    >>> from tool_helpers import ToolResponse, to_relative_path, truncate_with_recovery
    >>>
    >>> # Format a file read with automatic truncation and path conversion
    >>> response = ToolResponse.file_read_response(
    ...     content=file_content,
    ...     file_path="/abs/path/to/file.py",
    ...     working_dir="/abs/path"
    ... )
    >>> print(response.format_for_agent())
    ✅ Success
    File Path: to/file.py
    ...

Configuration:
    All limits can be configured via environment variables:
    - CF_LIMIT_FILE_READ_CHARS: Max chars for file reads (default: 500000)
    - CF_LIMIT_GREP_MATCHES: Max grep matches (default: 10000)
    - CF_USE_RELATIVE_PATHS: Use relative paths (default: true)
    - CF_ENABLE_TOKEN_COUNTING: Enable tiktoken (default: true)

    See ToolLimits class for full configuration options.
"""

# Version
__version__ = '1.0.0'

# Core configuration and limits
from .limits import (
    ToolLimits,
    get_default_limits,
    get_cached_default_limits,
    validate_limits,
    get_limit_for_operation,
    format_limits_summary
)

from .config import (
    ToolHelpersConfig,
    get_config,
    reset_config,
    print_config
)

# Path utilities
from .path_utils import (
    to_relative_path,
    to_absolute_path,
    is_within_project,
    format_tool_output_paths,
    format_file_path_for_display,
    normalize_path_separators,
    get_common_path_prefix,
    relativize_paths_in_dict
)

# Truncation utilities
from .truncation import (
    truncate_with_recovery,
    format_file_truncation,
    format_grep_truncation,
    format_command_truncation,
    truncate_line,
    count_tokens,
    format_token_count,
    TIKTOKEN_AVAILABLE
)

# Response formatting
from .response_formatter import (
    ToolResponse,
    format_file_read_output,
    format_grep_output,
    format_subprocess_output
)

# Public API
__all__ = [
    # Version
    '__version__',

    # Configuration
    'ToolLimits',
    'ToolHelpersConfig',
    'get_default_limits',
    'get_cached_default_limits',
    'validate_limits',
    'get_limit_for_operation',
    'format_limits_summary',
    'get_config',
    'reset_config',
    'print_config',

    # Path utilities
    'to_relative_path',
    'to_absolute_path',
    'is_within_project',
    'format_tool_output_paths',
    'format_file_path_for_display',
    'normalize_path_separators',
    'get_common_path_prefix',
    'relativize_paths_in_dict',

    # Truncation
    'truncate_with_recovery',
    'format_file_truncation',
    'format_grep_truncation',
    'format_command_truncation',
    'truncate_line',
    'count_tokens',
    'format_token_count',
    'TIKTOKEN_AVAILABLE',

    # Response formatting
    'ToolResponse',
    'format_file_read_output',
    'format_grep_output',
    'format_subprocess_output',
]


def get_version() -> str:
    """Get tool_helpers version.

    Returns:
        Version string
    """
    return __version__


def print_info():
    """Print tool_helpers information and configuration."""
    print(f"Tool Helpers v{__version__}")
    print("=" * 60)
    print("")
    print("A utility library for improving agent-tool interactions.")
    print("")
    print("Key features:")
    print("  • Smart truncation with recovery instructions")
    print("  • Relative path conversion (20-30% token savings)")
    print("  • Configurable limits and timeouts")
    print("  • Standardized tool response formatting")
    print("  • Token-aware truncation (tiktoken integration)")
    print("")
    print("=" * 60)
    print("")
    print_config()


if __name__ == '__main__':
    # When run as module, print info
    print_info()
