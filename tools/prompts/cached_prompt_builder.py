#!/usr/bin/env python3
"""
Cached Prompt Builder
Build orchestrator prompts with Anthropic cache control markers for 90% cost savings
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional


def build_cached_prompt(
    task_config: Dict[str, Any],
    orchestrator_prompt_path: str = "tools/orchestrator_prompt.txt",
    enable_caching: bool = True,
    cache_ttl: str = "5m"
) -> str:
    """
    Build orchestrator prompt with Anthropic cache control markers.

    Args:
        task_config: Task configuration dict (task, mode, working_dir, etc.)
        orchestrator_prompt_path: Path to orchestrator prompt template
        enable_caching: Enable/disable caching (default: True)
        cache_ttl: Cache TTL - "5m" or "1h" (default: "5m")

    Returns:
        Complete system prompt with cache markers and task configuration

    Strategy:
        1. Read orchestrator_prompt.txt
        2. Split at cache boundary marker
        3. Add cache control comment to static section
        4. Append dynamic task configuration
        5. Return combined prompt

    Cache Marker Format:
        The cache marker is a special comment that Claude Code recognizes:
        <!-- ANTHROPIC_CACHE_CONTROL: {"type": "ephemeral", "ttl": "5m"} -->

    Example:
        config = {"task": "Build app", "mode": "new_project", ...}
        prompt = build_cached_prompt(config)
        # Use with: claude --system-prompt <prompt>
    """
    # Load cache configuration
    from tools.prompts import CacheConfig
    cache_config = CacheConfig()

    # Check if caching should be enabled
    if not enable_caching or not cache_config.is_caching_enabled():
        # Return standard prompt without cache markers
        return _build_standard_prompt(task_config, orchestrator_prompt_path)

    # Read orchestrator prompt
    prompt_path = Path(orchestrator_prompt_path)
    if not prompt_path.exists():
        raise FileNotFoundError(f"Orchestrator prompt not found: {prompt_path}")

    with open(prompt_path, 'r') as f:
        orchestrator_content = f.read()

    # Find cache boundary marker
    cache_boundary = "<<CACHE_BOUNDARY_MARKER>>"

    if cache_boundary in orchestrator_content:
        # Split at boundary
        parts = orchestrator_content.split(cache_boundary, 1)
        static_section = parts[0].strip()
        dynamic_template = parts[1].strip() if len(parts) > 1 else ""
    else:
        # No boundary marker found - use heuristic
        # Find "BEGIN AUTONOMOUS EXECUTION NOW" and split there
        lines = orchestrator_content.split('\n')
        boundary_line = None

        for i, line in enumerate(lines):
            if "BEGIN EXECUTION NOW" in line or "START NOW" in line:
                boundary_line = i
                break

        if boundary_line:
            static_section = '\n'.join(lines[:boundary_line]).strip()
            dynamic_template = '\n'.join(lines[boundary_line:]).strip()
        else:
            # Can't find boundary - use last 50 lines as dynamic
            static_section = '\n'.join(lines[:-50]).strip()
            dynamic_template = '\n'.join(lines[-50:]).strip()

    # Validate static section meets minimum token requirement
    static_tokens = _estimate_tokens(static_section)
    min_tokens = cache_config.get_min_tokens()

    if static_tokens < min_tokens:
        print(f"⚠️ WARNING: Static section only {static_tokens} tokens (need {min_tokens}+)")
        print(f"   Caching disabled - section too small to cache")
        return _build_standard_prompt(task_config, orchestrator_prompt_path)

    # Build cache control marker
    cache_marker = f'\n\n<!-- ANTHROPIC_CACHE_CONTROL: {{"type": "ephemeral", "ttl": "{cache_ttl}"}} -->\n\n'

    # Build dynamic section with task configuration
    task_section = f"""AUTONOMOUS BUILD TASK

CONFIGURATION:
{json.dumps(task_config, indent=2)}

Execute the full Scout → Architect → Builder → Test → Deploy workflow.
{"Self-healing test loop is ENABLED. Fix and retry up to " + str(task_config.get("max_test_iterations", 3)) + " times if tests fail." if task_config.get("enable_test_loop", True) else "Test loop is DISABLED. Test once and proceed."}

Return JSON summary when complete.
BEGIN AUTONOMOUS EXECUTION NOW.
"""

    # Combine sections
    final_prompt = static_section + cache_marker + task_section

    # Log cache info
    print(f"✅ Prompt caching enabled:")
    print(f"   Static section: ~{static_tokens:,} tokens (cacheable)")
    print(f"   Dynamic section: ~{_estimate_tokens(task_section):,} tokens")
    print(f"   Cache TTL: {cache_ttl}")
    print(f"   Expected savings: 90% on cache hits\n")

    return final_prompt


def _build_standard_prompt(
    task_config: Dict[str, Any],
    orchestrator_prompt_path: str
) -> str:
    """
    Build standard prompt without cache markers (fallback).

    Args:
        task_config: Task configuration
        orchestrator_prompt_path: Path to prompt template

    Returns:
        Complete prompt without caching
    """
    prompt_path = Path(orchestrator_prompt_path)
    if not prompt_path.exists():
        raise FileNotFoundError(f"Orchestrator prompt not found: {prompt_path}")

    with open(prompt_path, 'r') as f:
        orchestrator_content = f.read()

    # Remove cache boundary marker if present
    orchestrator_content = orchestrator_content.replace("<<CACHE_BOUNDARY_MARKER>>", "")

    # Build task section
    task_section = f"""

AUTONOMOUS BUILD TASK

CONFIGURATION:
{json.dumps(task_config, indent=2)}

Execute the full Scout → Architect → Builder → Test → Deploy workflow.
{"Self-healing test loop is ENABLED. Fix and retry up to " + str(task_config.get("max_test_iterations", 3)) + " times if tests fail." if task_config.get("enable_test_loop", True) else "Test loop is DISABLED. Test once and proceed."}

Return JSON summary when complete.
BEGIN AUTONOMOUS EXECUTION NOW.
"""

    return orchestrator_content + task_section


def _estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.

    Uses simple heuristic: ~4 characters per token (Claude models).
    For accurate counting, would use anthropic.count_tokens() but that requires API key.

    Args:
        text: Text to count tokens for

    Returns:
        Estimated token count
    """
    # Simple estimation: 4 chars per token (slightly conservative)
    return len(text) // 4


def count_prompt_tokens(text: str, model: str = "claude-sonnet-4") -> int:
    """
    Count tokens in prompt using anthropic package (if available).

    Args:
        text: Text to count tokens for
        model: Model name for tokenization

    Returns:
        Accurate token count, or estimation if anthropic package unavailable
    """
    try:
        from anthropic import Anthropic
        client = Anthropic()

        # Use count_tokens method
        result = client.count_tokens(text)

        # Handle different response formats
        if isinstance(result, dict):
            return result.get('token_count', result.get('tokens', 0))
        elif isinstance(result, int):
            return result
        else:
            # Fallback to estimation
            return _estimate_tokens(text)

    except ImportError:
        # Anthropic package not available - use estimation
        return _estimate_tokens(text)
    except Exception:
        # API call failed or other error - use estimation
        return _estimate_tokens(text)


def get_prompt_hash(prompt: str) -> str:
    """
    Generate hash of prompt for version tracking.

    Args:
        prompt: Prompt text

    Returns:
        SHA256 hash (first 12 chars)
    """
    hash_obj = hashlib.sha256(prompt.encode('utf-8'))
    return hash_obj.hexdigest()[:12]


def validate_cache_markers(prompt: str) -> Dict[str, Any]:
    """
    Validate that cache markers are correctly placed in prompt.

    Args:
        prompt: Prompt with cache markers

    Returns:
        Validation result dict:
        {
            "valid": bool,
            "has_marker": bool,
            "marker_count": int,
            "marker_position": int,
            "issues": list[str]
        }
    """
    issues = []

    # Check for cache marker
    marker_pattern = "ANTHROPIC_CACHE_CONTROL"
    has_marker = marker_pattern in prompt
    marker_count = prompt.count(marker_pattern)

    if not has_marker:
        issues.append("No cache control marker found")

    if marker_count > 1:
        issues.append(f"Multiple cache markers found ({marker_count}) - should be 1")

    # Find marker position
    marker_position = prompt.find(marker_pattern) if has_marker else -1

    # Check marker is in correct position (should be after static content, before dynamic)
    if has_marker:
        # Marker should come before "AUTONOMOUS BUILD TASK"
        task_start = prompt.find("AUTONOMOUS BUILD TASK")
        if task_start == -1:
            issues.append("No task section found")
        elif marker_position > task_start:
            issues.append("Cache marker appears after task section (should be before)")

        # Marker should come after "ORCHESTRATOR AGENT" header
        header_pos = prompt.find("ORCHESTRATOR AGENT")
        if header_pos != -1 and marker_position < header_pos:
            issues.append("Cache marker appears before orchestrator header")

    return {
        "valid": len(issues) == 0,
        "has_marker": has_marker,
        "marker_count": marker_count,
        "marker_position": marker_position,
        "issues": issues
    }


# CLI interface for testing
if __name__ == "__main__":
    import sys

    print("Cached Prompt Builder - Test Mode\n")

    # Test configuration
    test_config = {
        "task": "Build a test application",
        "working_directory": "/tmp/test",
        "mode": "new_project",
        "enable_test_loop": True,
        "max_test_iterations": 3
    }

    # Build cached prompt
    print("Building cached prompt...\n")
    prompt = build_cached_prompt(
        task_config=test_config,
        orchestrator_prompt_path="tools/orchestrator_prompt.txt",
        enable_caching=True
    )

    # Validate
    validation = validate_cache_markers(prompt)
    print(f"\nValidation Results:")
    print(f"  Valid: {validation['valid']}")
    print(f"  Has marker: {validation['has_marker']}")
    print(f"  Marker count: {validation['marker_count']}")
    print(f"  Marker position: {validation['marker_position']}")

    if validation['issues']:
        print(f"\n  Issues:")
        for issue in validation['issues']:
            print(f"    - {issue}")

    # Show prompt stats
    print(f"\nPrompt Statistics:")
    print(f"  Total length: {len(prompt):,} characters")
    print(f"  Estimated tokens: ~{_estimate_tokens(prompt):,}")
    print(f"  Prompt hash: {get_prompt_hash(prompt)}")

    # Optionally save to file
    if len(sys.argv) > 1 and sys.argv[1] == "--save":
        output_path = "/tmp/cached_prompt_test.txt"
        with open(output_path, 'w') as f:
            f.write(prompt)
        print(f"\n✅ Saved prompt to: {output_path}")
