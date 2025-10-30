"""
Tool operation limits and configuration.

This module defines limits for all tool operations to prevent resource exhaustion,
provide consistent behavior, and improve agent experience.

Key principles:
- Sensible defaults based on Claude's 200K token context window
- Environment variable overrides for flexibility
- Validation with helpful error messages
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Tuple
import os


@dataclass
class ToolLimits:
    """Configuration for tool operation limits.

    All limits are designed to fit comfortably within Claude's 200K token context
    window while providing enough information for agents to work effectively.

    Token estimation: 1 token ≈ 4 characters
    - 200K tokens ≈ 800K characters total context
    - Reserve 100K tokens for prompt + response
    - Leaves 100K tokens (400K chars) for tool outputs
    """

    # File read limits
    max_file_read_lines: int = 50000  # Most files are < 5K lines
    max_file_read_chars: int = 500000  # ~125K tokens, leaves room for other context

    # Grep limits
    max_grep_matches: int = 10000  # Massive searches should be refined
    max_grep_output_chars: int = 300000  # ~75K tokens
    max_grep_line_length: int = 1000  # Truncate extremely long lines

    # Glob limits
    max_glob_files: int = 5000  # Most projects have < 1000 files
    max_glob_depth: int = 20  # Prevent infinite symlink loops

    # Subprocess limits
    subprocess_timeout_seconds: int = 120  # 2 minutes default
    subprocess_max_output_lines: int = 10000
    subprocess_max_output_chars: int = 200000  # ~50K tokens

    # Test execution limits (more generous)
    test_timeout_seconds: int = 300  # 5 minutes for test suites
    test_max_output_chars: int = 100000  # ~25K tokens (test output is important)

    # Build execution limits (even more generous)
    build_timeout_seconds: int = 600  # 10 minutes for builds
    build_max_output_chars: int = 150000  # ~37K tokens

    # Path handling
    use_relative_paths: bool = True  # Convert absolute → relative to save tokens

    # Token counting (optional, requires tiktoken)
    enable_token_counting: bool = True
    token_estimation_threshold: int = 40000  # Only count if content > 40KB

    # Truncation behavior
    truncation_strategy: str = "smart"  # "smart" or "simple"
    include_recovery_instructions: bool = True

    def __post_init__(self):
        """Validate limits after initialization."""
        is_valid, errors = validate_limits(self)
        if not is_valid:
            raise ValueError(f"Invalid limits configuration: {', '.join(errors)}")


def get_default_limits() -> ToolLimits:
    """Get default limits with environment variable overrides.

    Environment variables override defaults:
    - CF_LIMIT_FILE_READ_CHARS: Max chars for file reads
    - CF_LIMIT_FILE_READ_LINES: Max lines for file reads
    - CF_LIMIT_GREP_MATCHES: Max grep matches
    - CF_LIMIT_GREP_CHARS: Max chars for grep output
    - CF_LIMIT_GLOB_FILES: Max files for glob
    - CF_LIMIT_SUBPROCESS_TIMEOUT: Subprocess timeout in seconds
    - CF_LIMIT_TEST_TIMEOUT: Test timeout in seconds
    - CF_USE_RELATIVE_PATHS: "true" or "false"
    - CF_ENABLE_TOKEN_COUNTING: "true" or "false"

    Returns:
        ToolLimits instance with defaults or environment overrides

    Example:
        >>> limits = get_default_limits()
        >>> limits.max_file_read_chars
        500000

        >>> os.environ['CF_LIMIT_FILE_READ_CHARS'] = '100000'
        >>> limits = get_default_limits()
        >>> limits.max_file_read_chars
        100000
    """
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

    def get_bool_env(key: str, default: bool) -> bool:
        """Get boolean from environment or use default."""
        value = os.environ.get(key)
        if value is None:
            return default
        return value.lower() in ('true', '1', 'yes', 'on')

    return ToolLimits(
        max_file_read_lines=get_int_env('CF_LIMIT_FILE_READ_LINES', 50000),
        max_file_read_chars=get_int_env('CF_LIMIT_FILE_READ_CHARS', 500000),
        max_grep_matches=get_int_env('CF_LIMIT_GREP_MATCHES', 10000),
        max_grep_output_chars=get_int_env('CF_LIMIT_GREP_CHARS', 300000),
        max_grep_line_length=get_int_env('CF_LIMIT_GREP_LINE_LENGTH', 1000),
        max_glob_files=get_int_env('CF_LIMIT_GLOB_FILES', 5000),
        max_glob_depth=get_int_env('CF_LIMIT_GLOB_DEPTH', 20),
        subprocess_timeout_seconds=get_int_env('CF_LIMIT_SUBPROCESS_TIMEOUT', 120),
        subprocess_max_output_lines=get_int_env('CF_LIMIT_SUBPROCESS_LINES', 10000),
        subprocess_max_output_chars=get_int_env('CF_LIMIT_SUBPROCESS_CHARS', 200000),
        test_timeout_seconds=get_int_env('CF_LIMIT_TEST_TIMEOUT', 300),
        test_max_output_chars=get_int_env('CF_LIMIT_TEST_CHARS', 100000),
        build_timeout_seconds=get_int_env('CF_LIMIT_BUILD_TIMEOUT', 600),
        build_max_output_chars=get_int_env('CF_LIMIT_BUILD_CHARS', 150000),
        use_relative_paths=get_bool_env('CF_USE_RELATIVE_PATHS', True),
        enable_token_counting=get_bool_env('CF_ENABLE_TOKEN_COUNTING', True),
        token_estimation_threshold=get_int_env('CF_TOKEN_THRESHOLD', 40000),
        truncation_strategy=os.environ.get('CF_TRUNCATION_STRATEGY', 'smart'),
        include_recovery_instructions=get_bool_env('CF_INCLUDE_RECOVERY', True),
    )


def validate_limits(limits: ToolLimits) -> Tuple[bool, List[str]]:
    """Validate limits configuration.

    Args:
        limits: ToolLimits instance to validate

    Returns:
        Tuple of (is_valid, error_messages)

    Example:
        >>> limits = ToolLimits(max_file_read_chars=-1000)
        >>> is_valid, errors = validate_limits(limits)
        >>> is_valid
        False
        >>> 'max_file_read_chars' in errors[0]
        True
    """
    errors = []

    # Validate positive values
    positive_fields = [
        'max_file_read_lines', 'max_file_read_chars',
        'max_grep_matches', 'max_grep_output_chars', 'max_grep_line_length',
        'max_glob_files', 'max_glob_depth',
        'subprocess_timeout_seconds', 'subprocess_max_output_lines', 'subprocess_max_output_chars',
        'test_timeout_seconds', 'test_max_output_chars',
        'build_timeout_seconds', 'build_max_output_chars',
        'token_estimation_threshold'
    ]

    for field in positive_fields:
        value = getattr(limits, field)
        if value <= 0:
            errors.append(f"{field} must be positive, got {value}")

    # Validate reasonable ranges
    if limits.max_file_read_chars > 10_000_000:  # 10MB
        errors.append(f"max_file_read_chars too large: {limits.max_file_read_chars} (max 10M)")

    if limits.subprocess_timeout_seconds > 3600:  # 1 hour
        errors.append(f"subprocess_timeout_seconds too large: {limits.subprocess_timeout_seconds} (max 3600)")

    if limits.max_glob_depth > 100:
        errors.append(f"max_glob_depth too large: {limits.max_glob_depth} (max 100)")

    # Validate truncation strategy
    if limits.truncation_strategy not in ('smart', 'simple'):
        errors.append(f"truncation_strategy must be 'smart' or 'simple', got '{limits.truncation_strategy}'")

    return (len(errors) == 0, errors)


def get_limit_for_operation(operation_type: str, limits: ToolLimits = None) -> Dict[str, Any]:
    """Get specific limits for an operation type.

    Args:
        operation_type: One of 'file_read', 'grep', 'glob', 'subprocess', 'test', 'build'
        limits: ToolLimits instance (uses defaults if None)

    Returns:
        Dictionary of relevant limits for the operation

    Raises:
        ValueError: If operation_type is unknown

    Example:
        >>> limits = get_limit_for_operation('file_read')
        >>> limits['max_chars']
        500000
        >>> limits['max_lines']
        50000
    """
    if limits is None:
        limits = get_default_limits()

    operation_limits = {
        'file_read': {
            'max_lines': limits.max_file_read_lines,
            'max_chars': limits.max_file_read_chars,
            'use_relative_paths': limits.use_relative_paths,
        },
        'grep': {
            'max_matches': limits.max_grep_matches,
            'max_chars': limits.max_grep_output_chars,
            'max_line_length': limits.max_grep_line_length,
            'use_relative_paths': limits.use_relative_paths,
        },
        'glob': {
            'max_files': limits.max_glob_files,
            'max_depth': limits.max_glob_depth,
            'use_relative_paths': limits.use_relative_paths,
        },
        'subprocess': {
            'timeout_seconds': limits.subprocess_timeout_seconds,
            'max_output_lines': limits.subprocess_max_output_lines,
            'max_output_chars': limits.subprocess_max_output_chars,
        },
        'test': {
            'timeout_seconds': limits.test_timeout_seconds,
            'max_output_chars': limits.test_max_output_chars,
        },
        'build': {
            'timeout_seconds': limits.build_timeout_seconds,
            'max_output_chars': limits.build_max_output_chars,
        },
    }

    if operation_type not in operation_limits:
        valid_types = ', '.join(operation_limits.keys())
        raise ValueError(f"Unknown operation type '{operation_type}'. Valid types: {valid_types}")

    return operation_limits[operation_type]


def format_limits_summary(limits: ToolLimits = None) -> str:
    """Format limits as human-readable summary.

    Useful for debugging and logging configuration.

    Args:
        limits: ToolLimits instance (uses defaults if None)

    Returns:
        Formatted string with all limits

    Example:
        >>> print(format_limits_summary())
        Tool Limits Configuration:
        File Read: 50000 lines, 500000 chars (~125K tokens)
        ...
    """
    if limits is None:
        limits = get_default_limits()

    lines = ["Tool Limits Configuration:"]
    lines.append(f"  File Read: {limits.max_file_read_lines:,} lines, {limits.max_file_read_chars:,} chars (~{limits.max_file_read_chars//4:,} tokens)")
    lines.append(f"  Grep: {limits.max_grep_matches:,} matches, {limits.max_grep_output_chars:,} chars (~{limits.max_grep_output_chars//4:,} tokens)")
    lines.append(f"  Glob: {limits.max_glob_files:,} files, depth {limits.max_glob_depth}")
    lines.append(f"  Subprocess: {limits.subprocess_timeout_seconds}s timeout, {limits.subprocess_max_output_chars:,} chars")
    lines.append(f"  Test: {limits.test_timeout_seconds}s timeout, {limits.test_max_output_chars:,} chars")
    lines.append(f"  Build: {limits.build_timeout_seconds}s timeout, {limits.build_max_output_chars:,} chars")
    lines.append(f"  Paths: {'relative' if limits.use_relative_paths else 'absolute'}")
    lines.append(f"  Token Counting: {'enabled' if limits.enable_token_counting else 'disabled'}")
    lines.append(f"  Truncation: {limits.truncation_strategy} with recovery={'yes' if limits.include_recovery_instructions else 'no'}")

    return '\n'.join(lines)


# Singleton for default limits (avoids repeated environment variable reads)
_default_limits_cache: ToolLimits = None


def get_cached_default_limits() -> ToolLimits:
    """Get cached default limits (reads environment variables only once).

    Returns:
        Cached ToolLimits instance
    """
    global _default_limits_cache
    if _default_limits_cache is None:
        _default_limits_cache = get_default_limits()
    return _default_limits_cache
