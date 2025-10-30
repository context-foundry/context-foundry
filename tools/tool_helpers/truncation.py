"""
Smart truncation utilities for tool output.

This module provides intelligent truncation that includes recovery instructions,
helping agents know what to do when output is cut off.

Key principles:
- Always provide recovery instructions (tell agent how to get more data)
- Include context (what was truncated, how much remains)
- Token-aware truncation (use tiktoken when available)
- Operation-specific formatting (file reads vs grep vs subprocess)
"""

from typing import Optional, Dict, Any, Tuple
from .limits import ToolLimits, get_cached_default_limits


# Try to import tiktoken for accurate token counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
    _encoder = tiktoken.get_encoding("cl100k_base")  # Claude's encoding
except ImportError:
    TIKTOKEN_AVAILABLE = False
    _encoder = None


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken (if available) or estimate.

    Args:
        text: Text to count tokens for

    Returns:
        Number of tokens (exact if tiktoken available, estimated otherwise)
    """
    if TIKTOKEN_AVAILABLE and _encoder:
        return len(_encoder.encode(text))
    else:
        # Rough estimation: 1 token ≈ 4 characters
        return len(text) // 4


def truncate_with_recovery(
    content: str,
    max_chars: Optional[int] = None,
    max_lines: Optional[int] = None,
    file_path: Optional[str] = None,
    operation_type: str = "generic",
    limits: Optional[ToolLimits] = None
) -> Tuple[str, bool, Dict[str, Any]]:
    """Truncate content with recovery instructions.

    Args:
        content: Content to potentially truncate
        max_chars: Maximum characters (uses limits if None)
        max_lines: Maximum lines (uses limits if None)
        file_path: Path to file (for recovery instructions)
        operation_type: Type of operation (file_read, grep, subprocess, etc.)
        limits: ToolLimits instance (uses defaults if None)

    Returns:
        Tuple of (truncated_content, was_truncated, metadata)

        metadata includes:
        - original_chars: Original character count
        - original_lines: Original line count
        - truncated_chars: Truncated character count
        - truncated_lines: Truncated line count
        - truncation_reason: Why it was truncated
        - recovery_instructions: What to do next

    Example:
        >>> content = "line1\\n" * 100000
        >>> truncated, was_truncated, meta = truncate_with_recovery(
        ...     content, max_lines=1000, operation_type='file_read'
        ... )
        >>> was_truncated
        True
        >>> 'recovery_instructions' in meta
        True
    """
    if limits is None:
        limits = get_cached_default_limits()

    # Get defaults from limits if not specified
    if max_chars is None:
        from .limits import get_limit_for_operation
        op_limits = get_limit_for_operation(operation_type, limits)
        max_chars = op_limits.get('max_chars', 500000)

    if max_lines is None:
        from .limits import get_limit_for_operation
        op_limits = get_limit_for_operation(operation_type, limits)
        max_lines = op_limits.get('max_lines', 50000)

    # Count original
    lines = content.split('\n')
    original_lines = len(lines)
    original_chars = len(content)

    # Check if truncation needed
    needs_truncation_lines = original_lines > max_lines
    needs_truncation_chars = original_chars > max_chars

    if not (needs_truncation_lines or needs_truncation_chars):
        # No truncation needed
        return content, False, {
            'original_chars': original_chars,
            'original_lines': original_lines,
            'truncated_chars': original_chars,
            'truncated_lines': original_lines,
            'truncation_reason': None,
            'recovery_instructions': None
        }

    # Perform truncation
    truncation_reason = []
    if needs_truncation_lines:
        truncation_reason.append(f"exceeded {max_lines:,} line limit")
        lines = lines[:max_lines]

    truncated_content = '\n'.join(lines)

    if len(truncated_content) > max_chars:
        truncation_reason.append(f"exceeded {max_chars:,} character limit")
        truncated_content = truncated_content[:max_chars]

    # Generate recovery instructions based on operation type
    recovery = _generate_recovery_instructions(
        operation_type=operation_type,
        file_path=file_path,
        original_lines=original_lines,
        original_chars=original_chars,
        truncated_lines=len(lines),
        truncated_chars=len(truncated_content),
        max_lines=max_lines,
        max_chars=max_chars
    )

    metadata = {
        'original_chars': original_chars,
        'original_lines': original_lines,
        'truncated_chars': len(truncated_content),
        'truncated_lines': len(lines) if needs_truncation_lines else original_lines,
        'truncation_reason': ' and '.join(truncation_reason),
        'recovery_instructions': recovery
    }

    return truncated_content, True, metadata


def _generate_recovery_instructions(
    operation_type: str,
    file_path: Optional[str],
    original_lines: int,
    original_chars: int,
    truncated_lines: int,
    truncated_chars: int,
    max_lines: int,
    max_chars: int
) -> str:
    """Generate operation-specific recovery instructions.

    Args:
        operation_type: Type of operation
        file_path: Path to file (if applicable)
        original_lines: Original line count
        original_chars: Original character count
        truncated_lines: Truncated line count
        truncated_chars: Truncated character count
        max_lines: Maximum lines allowed
        max_chars: Maximum characters allowed

    Returns:
        Recovery instructions text
    """
    remaining_lines = original_lines - truncated_lines
    remaining_chars = original_chars - truncated_chars

    if operation_type == 'file_read':
        return _file_read_recovery(file_path, truncated_lines, original_lines, remaining_lines)
    elif operation_type == 'grep':
        return _grep_recovery(truncated_lines, original_lines)
    elif operation_type == 'subprocess':
        return _subprocess_recovery(truncated_chars, original_chars)
    elif operation_type == 'glob':
        return _glob_recovery(truncated_lines, original_lines)
    else:
        return _generic_recovery(truncated_lines, truncated_chars, remaining_lines, remaining_chars)


def _file_read_recovery(file_path: Optional[str], shown_lines: int, total_lines: int, remaining: int) -> str:
    """Generate recovery instructions for file reads."""
    instructions = [
        f"Output truncated. Showing lines 1-{shown_lines:,} of {total_lines:,} total lines.",
        f"Remaining: {remaining:,} lines not shown.",
        "",
        "To read more:"
    ]

    if file_path:
        next_offset = shown_lines
        instructions.extend([
            f"  • Use: read_file(path='{file_path}', offset={next_offset:,}, limit=5000)",
            f"  • Or: read_file(path='{file_path}', offset={next_offset:,})",
        ])
    else:
        instructions.append("  • Use offset parameter to read next section")

    instructions.extend([
        "  • Or: Use grep with more specific pattern to reduce results",
        "  • Or: Specify line numbers for targeted reading"
    ])

    return '\n'.join(instructions)


def _grep_recovery(matches_shown: int, total_matches: int) -> str:
    """Generate recovery instructions for grep results."""
    instructions = [
        f"Output truncated. Showing {matches_shown:,} of {total_matches:,} total matches.",
        "",
        "To refine search:",
        "  • Use more specific search pattern",
        "  • Add file type filter (e.g., --type=py)",
        "  • Search in specific directory",
        "  • Use head_limit parameter for top N results only"
    ]

    return '\n'.join(instructions)


def _subprocess_recovery(shown_chars: int, total_chars: int) -> str:
    """Generate recovery instructions for subprocess output."""
    instructions = [
        f"Command output truncated at {shown_chars:,} of {total_chars:,} characters.",
        "",
        "Options:",
        "  • Review the output shown (may contain critical errors)",
        "  • Re-run command with filters to reduce output",
        "  • Check command exit code for errors",
        "  • Redirect output to file if full output needed"
    ]

    return '\n'.join(instructions)


def _glob_recovery(files_shown: int, total_files: int) -> str:
    """Generate recovery instructions for glob results."""
    instructions = [
        f"File list truncated. Showing {files_shown:,} of {total_files:,} total files.",
        "",
        "To narrow results:",
        "  • Use more specific glob pattern",
        "  • Search in specific subdirectory",
        "  • Filter by file extension",
        "  • Use find command with additional filters"
    ]

    return '\n'.join(instructions)


def _generic_recovery(shown_lines: int, shown_chars: int, remaining_lines: int, remaining_chars: int) -> str:
    """Generate generic recovery instructions."""
    instructions = [
        f"Output truncated at {shown_lines:,} lines / {shown_chars:,} characters.",
        f"Remaining: {remaining_lines:,} lines / {remaining_chars:,} characters not shown.",
        "",
        "Options:",
        "  • Review the output shown for key information",
        "  • Refine your query to be more specific",
        "  • Request specific sections if needed"
    ]

    return '\n'.join(instructions)


def format_file_truncation(
    content: str,
    file_path: str,
    limits: Optional[ToolLimits] = None
) -> Tuple[str, Dict[str, Any]]:
    """Format truncated file content with recovery instructions.

    Convenience function for file read operations.

    Args:
        content: File content
        file_path: Path to file
        limits: ToolLimits instance (uses defaults if None)

    Returns:
        Tuple of (formatted_content, metadata)

    Example:
        >>> content = "line\\n" * 100000
        >>> formatted, meta = format_file_truncation(content, "tools/cache.py")
        >>> meta['was_truncated']
        True
    """
    truncated, was_truncated, meta = truncate_with_recovery(
        content=content,
        file_path=file_path,
        operation_type='file_read',
        limits=limits
    )

    if not was_truncated:
        return content, {'was_truncated': False, **meta}

    # Add recovery instructions to output
    output_parts = [
        truncated,
        "",
        "═" * 60,
        "⚠️  FILE TRUNCATED",
        "═" * 60,
        meta['recovery_instructions']
    ]

    formatted = '\n'.join(output_parts)

    return formatted, {'was_truncated': True, **meta}


def format_grep_truncation(
    results: str,
    pattern: str,
    limits: Optional[ToolLimits] = None
) -> Tuple[str, Dict[str, Any]]:
    """Format truncated grep results with recovery instructions.

    Args:
        results: Grep results
        pattern: Search pattern used
        limits: ToolLimits instance (uses defaults if None)

    Returns:
        Tuple of (formatted_results, metadata)
    """
    truncated, was_truncated, meta = truncate_with_recovery(
        content=results,
        operation_type='grep',
        limits=limits
    )

    if not was_truncated:
        return results, {'was_truncated': False, **meta}

    output_parts = [
        truncated,
        "",
        "═" * 60,
        f"⚠️  GREP RESULTS TRUNCATED (Pattern: {pattern})",
        "═" * 60,
        meta['recovery_instructions']
    ]

    formatted = '\n'.join(output_parts)

    return formatted, {'was_truncated': True, **meta}


def format_command_truncation(
    output: str,
    command: str,
    exit_code: int = 0,
    limits: Optional[ToolLimits] = None
) -> Tuple[str, Dict[str, Any]]:
    """Format truncated command output with recovery instructions.

    Args:
        output: Command output
        command: Command that was run
        exit_code: Command exit code
        limits: ToolLimits instance (uses defaults if None)

    Returns:
        Tuple of (formatted_output, metadata)
    """
    truncated, was_truncated, meta = truncate_with_recovery(
        content=output,
        operation_type='subprocess',
        limits=limits
    )

    if not was_truncated:
        return output, {'was_truncated': False, 'exit_code': exit_code, **meta}

    output_parts = [
        truncated,
        "",
        "═" * 60,
        f"⚠️  COMMAND OUTPUT TRUNCATED (Exit code: {exit_code})",
        f"Command: {command}",
        "═" * 60,
        meta['recovery_instructions']
    ]

    formatted = '\n'.join(output_parts)

    return formatted, {'was_truncated': True, 'exit_code': exit_code, **meta}


def truncate_line(line: str, max_length: int = 1000) -> str:
    """Truncate a single very long line.

    Useful for preventing single-line files (minified JS, etc.) from
    overwhelming output.

    Args:
        line: Line to truncate
        max_length: Maximum length

    Returns:
        Truncated line

    Example:
        >>> truncate_line("a" * 2000, max_length=100)
        'aaaa...aaaa (1900 chars truncated)'
    """
    if len(line) <= max_length:
        return line

    # Keep first and last parts
    keep = max_length // 2 - 20  # Leave room for "..." and message
    if keep < 10:
        keep = 10

    truncated_count = len(line) - (keep * 2)
    return f"{line[:keep]}...{line[-keep:]} ({truncated_count:,} chars truncated)"


def format_token_count(content: str) -> str:
    """Format content with token count information.

    Args:
        content: Content to analyze

    Returns:
        Formatted string with token count

    Example:
        >>> format_token_count("Hello world!")
        'Content: 12 chars, ~3 tokens'
    """
    chars = len(content)
    tokens = count_tokens(content)
    token_type = "exact" if TIKTOKEN_AVAILABLE else "estimated"

    return f"Content: {chars:,} chars, ~{tokens:,} tokens ({token_type})"
