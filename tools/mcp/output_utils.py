"""
Output Formatting and Truncation Utilities

Pure utility functions for formatting and truncating command output.
Extracted from tools/mcp_server.py for better code organization.
"""


def truncate_output(output: str, max_tokens: int = 20000) -> tuple[str, bool, dict]:
    """
    Truncate large output to fit within token limits while preserving critical info.

    Args:
        output: The stdout or stderr string to potentially truncate
        max_tokens: Maximum tokens allowed (default 20000 to leave room for JSON structure)

    Returns:
        Tuple of (truncated_output, was_truncated, stats_dict)
        - truncated_output: The output string (truncated if needed)
        - was_truncated: Boolean indicating if truncation occurred
        - stats_dict: Dictionary with total_lines, total_chars, etc.
    """
    if not output:
        return output, False, {"total_lines": 0, "total_chars": 0}

    # Rough heuristic: ~4 chars per token
    max_chars = max_tokens * 4

    lines = output.split("\n")
    total_lines = len(lines)
    total_chars = len(output)

    # If output is small enough, return as-is
    if total_chars <= max_chars:
        return output, False, {"total_lines": total_lines, "total_chars": total_chars}

    # Calculate how many characters to keep from start and end
    # Keep 45% from start, 45% from end, 10% for truncation message
    chars_per_section = int(max_chars * 0.45)

    # Find split points by character count
    start_chars = 0
    start_line_idx = 0
    for i, line in enumerate(lines):
        start_chars += len(line) + 1  # +1 for newline
        if start_chars >= chars_per_section:
            start_line_idx = i
            break

    end_chars = 0
    end_line_idx = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        end_chars += len(lines[i]) + 1  # +1 for newline
        if end_chars >= chars_per_section:
            end_line_idx = i
            break

    # Build truncated output
    start_section = "\n".join(lines[:start_line_idx])
    end_section = "\n".join(lines[end_line_idx:])

    truncated_lines = end_line_idx - start_line_idx
    truncation_message = f"\n\n{'=' * 60}\n[OUTPUT TRUNCATED]\nShowing: First {start_line_idx} lines + Last {len(lines) - end_line_idx} lines\nHidden: {truncated_lines} lines ({total_chars - len(start_section) - len(end_section):,} chars)\nTotal: {total_lines:,} lines ({total_chars:,} chars)\n{'=' * 60}\n\n"

    truncated_output = start_section + truncation_message + end_section

    return (
        truncated_output,
        True,
        {
            "total_lines": total_lines,
            "total_chars": total_chars,
            "truncated_lines": truncated_lines,
            "kept_start_lines": start_line_idx,
            "kept_end_lines": len(lines) - end_line_idx,
        },
    )


def create_output_summary(output: str, max_lines: int = 50) -> tuple[str, dict]:
    """
    Create a smart summary of output showing first and last N lines.

    Args:
        output: Full output string
        max_lines: Number of lines to show from start and end (default 50)

    Returns:
        Tuple of (summary_output, stats_dict)
        - summary_output: Summarized output string
        - stats_dict: Dictionary with total_lines, shown_lines, hidden_lines
    """
    if not output:
        return "(empty)", {"total_lines": 0, "shown_lines": 0, "hidden_lines": 0}

    lines = output.split("\n")
    total_lines = len(lines)

    # If output is small enough, return as-is
    if total_lines <= (max_lines * 2):
        return output, {
            "total_lines": total_lines,
            "shown_lines": total_lines,
            "hidden_lines": 0,
        }

    # Get first and last N lines
    first_lines = lines[:max_lines]
    last_lines = lines[-max_lines:]
    hidden_lines = total_lines - (max_lines * 2)

    # Build summary
    separator = f"\n\n{'=' * 60}\n[{hidden_lines:,} lines hidden - see output_file for full content]\n{'=' * 60}\n\n"
    summary = "\n".join(first_lines) + separator + "\n".join(last_lines)

    return summary, {
        "total_lines": total_lines,
        "shown_lines": max_lines * 2,
        "hidden_lines": hidden_lines,
    }
