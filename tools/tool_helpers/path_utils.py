"""
Path utilities for tool helpers.

This module provides utilities for converting between absolute and relative paths,
which significantly reduces token usage in tool outputs.

Token savings example:
- Absolute: /Users/name/homelab/context-foundry/tools/cache/cache_manager.py (57 chars)
- Relative: tools/cache/cache_manager.py (30 chars)
- Savings: 47% reduction per path

In a typical build with 200+ file paths, this saves 5000+ tokens.
"""

from pathlib import Path
from typing import Union, Optional
import os
import re


def to_relative_path(
    path: Union[str, Path],
    working_dir: Union[str, Path] = None,
    strict: bool = False
) -> str:
    """Convert absolute path to relative path from working directory.

    Args:
        path: Absolute or relative path to convert
        working_dir: Working directory (defaults to current directory)
        strict: If True, raise error if path is outside working_dir

    Returns:
        Relative path as string

    Raises:
        ValueError: If strict=True and path is outside working_dir

    Example:
        >>> to_relative_path('/Users/name/homelab/context-foundry/tools/cache.py',
        ...                  '/Users/name/homelab/context-foundry')
        'tools/cache.py'

        >>> to_relative_path('tools/cache.py', '/Users/name/homelab/context-foundry')
        'tools/cache.py'  # Already relative, returned as-is
    """
    if working_dir is None:
        working_dir = os.getcwd()

    path = Path(path)
    working_dir = Path(working_dir).resolve()

    # If path is already relative, return it
    if not path.is_absolute():
        return str(path)

    try:
        path = path.resolve()
        relative = path.relative_to(working_dir)
        return str(relative)
    except ValueError:
        # Path is outside working_dir
        if strict:
            raise ValueError(f"Path {path} is outside working directory {working_dir}")

        # Return absolute path if outside working dir
        return str(path)


def to_absolute_path(
    path: Union[str, Path],
    working_dir: Union[str, Path] = None
) -> str:
    """Convert relative path to absolute path.

    Args:
        path: Relative or absolute path
        working_dir: Working directory (defaults to current directory)

    Returns:
        Absolute path as string

    Example:
        >>> to_absolute_path('tools/cache.py', '/Users/name/homelab/context-foundry')
        '/Users/name/homelab/context-foundry/tools/cache.py'
    """
    if working_dir is None:
        working_dir = os.getcwd()

    path = Path(path)
    if path.is_absolute():
        return str(path.resolve())

    working_dir = Path(working_dir).resolve()
    return str((working_dir / path).resolve())


def is_within_project(
    path: Union[str, Path],
    working_dir: Union[str, Path] = None
) -> bool:
    """Check if path is within the project working directory.

    Args:
        path: Path to check
        working_dir: Working directory (defaults to current directory)

    Returns:
        True if path is within working_dir, False otherwise

    Example:
        >>> is_within_project('/Users/name/homelab/context-foundry/tools/cache.py',
        ...                   '/Users/name/homelab/context-foundry')
        True

        >>> is_within_project('/etc/passwd', '/Users/name/homelab/context-foundry')
        False
    """
    if working_dir is None:
        working_dir = os.getcwd()

    try:
        path = Path(path).resolve()
        working_dir = Path(working_dir).resolve()
        path.relative_to(working_dir)
        return True
    except ValueError:
        return False


def format_tool_output_paths(
    output: str,
    working_dir: Union[str, Path] = None,
    preserve_patterns: list = None
) -> str:
    """Convert all absolute paths in tool output to relative paths.

    This function scans text output for absolute paths and converts them
    to relative paths, significantly reducing token usage.

    Args:
        output: Tool output text containing paths
        working_dir: Working directory (defaults to current directory)
        preserve_patterns: List of regex patterns for paths to preserve absolute
                          (e.g., system paths like /usr/bin/python)

    Returns:
        Output with paths converted to relative

    Example:
        >>> output = "Error in /Users/name/homelab/context-foundry/tools/cache.py:42"
        >>> format_tool_output_paths(output, '/Users/name/homelab/context-foundry')
        'Error in tools/cache.py:42'
    """
    if working_dir is None:
        working_dir = os.getcwd()

    working_dir = Path(working_dir).resolve()

    # Default patterns to preserve (system paths)
    default_preserve = [
        r'^/usr/',
        r'^/bin/',
        r'^/sbin/',
        r'^/lib/',
        r'^/etc/',
        r'^/System/',
        r'^/Library/',
        r'^C:\\Windows\\',
        r'^C:\\Program Files',
    ]

    preserve_patterns = preserve_patterns or default_preserve

    # Find all absolute paths in output
    # Matches Unix paths: /path/to/file or Windows paths: C:\path\to\file
    path_pattern = r'(?:[A-Z]:\\|/)(?:[^\s:,;"\'\n]+)'

    def replace_path(match):
        path_str = match.group(0)

        # Check if path should be preserved
        for pattern in preserve_patterns:
            if re.match(pattern, path_str):
                return path_str

        # Try to convert to relative
        try:
            relative = to_relative_path(path_str, working_dir, strict=False)
            return relative
        except Exception:
            # If conversion fails, return original
            return path_str

    return re.sub(path_pattern, replace_path, output)


def format_file_path_for_display(
    path: Union[str, Path],
    working_dir: Union[str, Path] = None,
    max_length: Optional[int] = None
) -> str:
    """Format a file path for display in tool output.

    Converts to relative path and optionally truncates if too long.

    Args:
        path: File path
        working_dir: Working directory (defaults to current directory)
        max_length: Maximum length (truncates middle if exceeded)

    Returns:
        Formatted path for display

    Example:
        >>> format_file_path_for_display(
        ...     '/Users/name/homelab/context-foundry/tools/cache/cache_manager.py',
        ...     '/Users/name/homelab/context-foundry',
        ...     max_length=30
        ... )
        'tools/.../cache_manager.py'
    """
    relative = to_relative_path(path, working_dir)

    if max_length is None or len(relative) <= max_length:
        return relative

    # Truncate middle with ...
    # Keep first and last parts
    parts = Path(relative).parts
    if len(parts) <= 2:
        return relative

    # Try to fit: first/.../ last
    first = parts[0]
    last = parts[-1]
    truncated = f"{first}/.../{last}"

    if len(truncated) <= max_length:
        return truncated

    # Still too long, truncate last part
    max_last = max_length - len(first) - 5  # "/.../..."
    if max_last > 10:
        last_truncated = last[:max_last-3] + "..."
        return f"{first}/.../{last_truncated}"

    # Give up, just truncate the whole thing
    return relative[:max_length-3] + "..."


def normalize_path_separators(path: str) -> str:
    """Normalize path separators to forward slashes (Unix-style).

    This ensures consistent path representation across platforms and
    further reduces token usage by using shorter forward slashes.

    Args:
        path: Path with any separator style

    Returns:
        Path with forward slashes

    Example:
        >>> normalize_path_separators('tools\\\\cache\\\\manager.py')
        'tools/cache/manager.py'
    """
    return path.replace('\\\\', '/').replace('\\', '/')


def get_common_path_prefix(paths: list[Union[str, Path]]) -> str:
    """Find common prefix of multiple paths.

    Useful for determining working directory from a list of paths.

    Args:
        paths: List of paths

    Returns:
        Common prefix path

    Example:
        >>> paths = [
        ...     '/Users/name/homelab/context-foundry/tools/cache.py',
        ...     '/Users/name/homelab/context-foundry/tools/metrics.py',
        ...     '/Users/name/homelab/context-foundry/tests/test.py'
        ... ]
        >>> get_common_path_prefix(paths)
        '/Users/name/homelab/context-foundry'
    """
    if not paths:
        return ""

    paths = [Path(p).resolve() for p in paths]

    # Start with first path
    common = paths[0]

    # Find common parent
    for path in paths[1:]:
        while not str(path).startswith(str(common)):
            common = common.parent
            if common == common.parent:  # Reached root
                break

    return str(common)


def relativize_paths_in_dict(
    data: dict,
    working_dir: Union[str, Path] = None,
    path_keys: list[str] = None
) -> dict:
    """Convert absolute paths in dictionary values to relative paths.

    Recursively processes nested dictionaries and lists.

    Args:
        data: Dictionary potentially containing paths
        working_dir: Working directory (defaults to current directory)
        path_keys: List of key names that contain paths (if None, checks all string values)

    Returns:
        Dictionary with relative paths

    Example:
        >>> data = {
        ...     'file': '/Users/name/homelab/context-foundry/tools/cache.py',
        ...     'line': 42
        ... }
        >>> relativize_paths_in_dict(data, '/Users/name/homelab/context-foundry')
        {'file': 'tools/cache.py', 'line': 42}
    """
    if working_dir is None:
        working_dir = os.getcwd()

    def process_value(value):
        if isinstance(value, dict):
            return relativize_paths_in_dict(value, working_dir, path_keys)
        elif isinstance(value, list):
            return [process_value(item) for item in value]
        elif isinstance(value, str):
            # Check if this looks like a path
            if '/' in value or '\\' in value:
                # Try to convert to relative
                try:
                    return to_relative_path(value, working_dir, strict=False)
                except Exception:
                    return value
            return value
        else:
            return value

    result = {}
    for key, value in data.items():
        if path_keys is None or key in path_keys:
            result[key] = process_value(value)
        else:
            result[key] = value

    return result
