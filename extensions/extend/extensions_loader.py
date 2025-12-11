"""
Workday Extend Extension Loader for Context Foundry.

Provides extension detection and loading capabilities.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import detector


def load_extension_detectors() -> Dict[str, Any]:
    """
    Load Extend extension detectors.

    Returns:
        Dictionary mapping extension name to detector module.

    Example:
        >>> detectors = load_extension_detectors()
        >>> if "extend" in detectors:
        ...     result = detectors["extend"].detect_extend_project(path)
    """
    return {
        "extend": detector
    }


def get_extension_claude_md() -> str:
    """
    Get the content of the extension's CLAUDE.md file.

    Returns:
        Content of CLAUDE.md as a string.

    Example:
        >>> context = get_extension_claude_md()
        >>> # Inject into phase prompt
    """
    extension_dir = Path(__file__).parent
    claude_md_path = extension_dir / "CLAUDE.md"

    if claude_md_path.exists():
        return claude_md_path.read_text(encoding="utf-8")
    return ""


def get_extension_info() -> Dict[str, Any]:
    """
    Get metadata about the Extend extension.

    Returns:
        Dictionary with extension metadata.
    """
    return {
        "name": "extend",
        "display_name": "Workday Extend",
        "description": "Build production-quality Workday Extend applications using PMD",
        "version": "2.1.0",
        "skip_phases": ["Screenshot", "Deploy"],  # Phases that don't apply to Extend
        "custom_phases": {
            "Architect": "phase_architect_extend.txt",  # PMD-specific architecture design
            "Builder": "phase_builder_extend.txt",      # PMD-specific building
            "Test": "phase_test_extend.txt"             # PMD quality validation
        },
        "languages": ["PMD", "JSON"],
        "project_type": "workday-extend"
    }


def get_extension_patterns(pattern_type: str = "common-issues") -> Optional[Dict[str, Any]]:
    """
    Get extension-specific patterns (NOT global patterns).

    These patterns are scoped to Extend projects only and should NOT be
    merged into global pattern storage. They're loaded only when building
    Extend applications.

    Args:
        pattern_type: Type of patterns ("common-issues" currently supported)

    Returns:
        Dictionary with patterns data, or None if not found.

    Example:
        >>> patterns = get_extension_patterns("common-issues")
        >>> if patterns:
        ...     for p in patterns.get("patterns", []):
        ...         print(p["id"], p["severity"])
    """
    extension_dir = Path(__file__).parent
    pattern_files = {
        "common-issues": "extend-common-issues.json",
    }

    if pattern_type not in pattern_files:
        return None

    pattern_path = extension_dir / "patterns" / pattern_files[pattern_type]

    if not pattern_path.exists():
        return None

    try:
        with open(pattern_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def get_extension_patterns_summary(
    severity_filter: Optional[List[str]] = None,
    max_patterns: int = 20
) -> str:
    """
    Get extension patterns formatted for prompt injection.

    Returns a markdown-formatted summary of common issues to watch for,
    suitable for injecting into phase prompts. Only loaded for Extend projects.

    Args:
        severity_filter: List of severities to include (e.g., ["high", "medium"])
                        Default: ["high"] for focused guidance
        max_patterns: Maximum patterns to include (default 20)

    Returns:
        Markdown-formatted patterns summary, or empty string if none found.

    Example:
        >>> summary = get_extension_patterns_summary(["high", "medium"])
        >>> # Inject into phase prompt for Extend builds
    """
    if severity_filter is None:
        severity_filter = ["high"]  # Focus on critical issues by default

    patterns_data = get_extension_patterns("common-issues")
    if not patterns_data:
        return ""

    patterns = patterns_data.get("patterns", [])
    if not patterns:
        return ""

    # Filter by severity
    filtered = [p for p in patterns if p.get("severity") in severity_filter]

    # Limit count
    filtered = filtered[:max_patterns]

    if not filtered:
        return ""

    # Format as markdown
    lines = [
        "## Extend Common Issues to Avoid",
        "",
        "These patterns have been learned from previous Extend builds:",
        "",
    ]

    for p in filtered:
        lines.append(f"### {p['id']}")
        lines.append(f"**Severity:** {p.get('severity', 'unknown').upper()}")
        lines.append(f"**Issue:** {p.get('description', 'No description')}")
        lines.append(f"**Solution:** {p.get('solution', 'No solution')}")
        if p.get("example_bad"):
            lines.append(f"**Bad:** `{p['example_bad']}`")
        if p.get("example_good"):
            lines.append(f"**Good:** `{p['example_good']}`")
        lines.append("")

    return "\n".join(lines)
