#!/usr/bin/env python3
"""
Smoke test for Scout BAML CLI parsing performance.

This test verifies that:
1. Claude CLI is available and functional
2. Scout parsing completes without timeout
3. Fallback to GPT-4o-mini BAML works if CLI unavailable
4. Timing data is captured for performance validation

Run: python3 tests/smoke_test_scout_cli.py
"""

import os
import sys
import time
import json
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test data: minimal Scout report markdown
TEST_SCOUT_MARKDOWN = """# Scout Report

## Executive Summary
This is a smoke test for validating Claude CLI integration with Scout BAML parsing.
The test verifies that parsing completes without timeout and produces valid JSON.

## Past Learnings Applied
- Use structured logging for debugging
- Implement proper error handling with fallbacks
- Add timeout protection for external API calls

## Known Risks
- Claude CLI dependency may not be available in all environments
- Network latency could affect parsing times
- MCP server initialization could cause hangs

## Key Requirements
- REQ-1: Parse Scout markdown in under 30 seconds
- REQ-2: Validate output against BAML schema
- REQ-3: Fall back to GPT-4o-mini if CLI unavailable

## Tech Stack

### Languages
- Python 3.11+

### Frameworks
- FastAPI for REST API
- BAML for structured LLM outputs

### Dependencies
- baml-py>=0.211.0
- claude CLI (Claude Code subscription)

### Justification
FastAPI provides async support and automatic OpenAPI documentation.
BAML ensures type-safe LLM responses with schema validation.

## Architecture Recommendations
1. Use async/await for I/O-bound operations
2. Implement caching layer for repeated queries
3. Add monitoring and alerting for timeout detection

## Main Challenges

### Challenge 1: Timeout Prevention
**Severity**: HIGH
**Mitigation**: Remove --strict-mcp-config flag to avoid MCP server initialization hangs

### Challenge 2: Fallback Reliability
**Severity**: MEDIUM
**Mitigation**: Test both Claude CLI and GPT-4o-mini paths with timing validation

## Testing Approach
- Unit tests for individual parsing functions
- Integration tests with mock Scout reports
- Smoke tests with timing capture and log artifacts

## Timeline Estimate
10-15 seconds for Claude CLI path, 7-8 seconds for GPT-4o-mini fallback
"""


def check_claude_cli_available():
    """Check if Claude CLI is available and get version."""
    if not shutil.which("claude"):
        return False, None

    try:
        result = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=5
        )
        version = result.stdout.strip() if result.returncode == 0 else "unknown"
        return True, version
    except Exception as e:
        return False, str(e)


def test_scout_parse_with_cli():
    """Test Scout parsing using Claude CLI."""
    print("\n" + "=" * 60)
    print("TEST 1: Scout Parsing with Claude CLI")
    print("=" * 60)

    # Force Claude CLI mode
    os.environ["BAML_USE_CLAUDE_CLI"] = "true"
    env_state = {
        "BAML_USE_CLAUDE_CLI": os.getenv("BAML_USE_CLAUDE_CLI"),
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
    }

    from tools.baml_integration import parse_scout_markdown_baml

    start_time = time.time()
    try:
        result = parse_scout_markdown_baml(TEST_SCOUT_MARKDOWN)
        elapsed = time.time() - start_time

        # Assert reasonable timing (should be < 30s, warn if > 20s)
        if elapsed > 30:
            raise AssertionError(f"Parse took {elapsed:.2f}s, exceeds 30s threshold")
        elif elapsed > 20:
            print(f"⚠️  WARNING: Parse took {elapsed:.2f}s (> 20s)")
            timing_assertion = "warn_gt_20s"
        else:
            timing_assertion = "pass"

        print(f"✅ SUCCESS: Parse completed in {elapsed:.2f}s")
        print(f"   Keys present: {list(result.keys())}")
        print(
            f"   Executive summary length: {len(result.get('executive_summary', ''))} chars"
        )

        return {
            "success": True,
            "method": "claude_cli",
            "elapsed_seconds": elapsed,
            "keys": list(result.keys()),
            "error": None,
            "env_state": env_state,
            "timing_assertion": timing_assertion,
        }
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ FAILED after {elapsed:.2f}s: {e}")
        return {
            "success": False,
            "method": "claude_cli",
            "elapsed_seconds": elapsed,
            "keys": None,
            "error": str(e),
            "env_state": env_state,
            "timing_assertion": "fail",
        }


def test_scout_parse_fallback():
    """Test Scout parsing fallback to GPT-4o-mini BAML."""
    print("\n" + "=" * 60)
    print("TEST 2: Scout Parsing Fallback (GPT-4o-mini)")
    print("=" * 60)

    # Check if OpenAI API key available
    if not os.getenv("OPENAI_API_KEY"):
        print("⏭️  SKIPPED: OPENAI_API_KEY not set")
        return {
            "success": None,
            "method": "gpt4o_mini",
            "elapsed_seconds": 0,
            "error": "OPENAI_API_KEY not set",
            "env_state": {"BAML_USE_CLAUDE_CLI": "false", "OPENAI_API_KEY": False},
            "timing_assertion": "skipped",
        }

    # Disable Claude CLI to force fallback
    os.environ["BAML_USE_CLAUDE_CLI"] = "false"
    env_state = {
        "BAML_USE_CLAUDE_CLI": os.getenv("BAML_USE_CLAUDE_CLI"),
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
    }

    # Force reload module to pick up env change
    if "tools.baml_integration" in sys.modules:
        del sys.modules["tools.baml_integration"]

    from tools.baml_integration import parse_scout_markdown_baml

    start_time = time.time()
    try:
        result = parse_scout_markdown_baml(TEST_SCOUT_MARKDOWN)
        elapsed = time.time() - start_time

        # Assert reasonable timing for fallback (should be < 30s, warn if > 20s)
        if elapsed > 30:
            raise AssertionError(
                f"Fallback parse took {elapsed:.2f}s, exceeds 30s threshold"
            )
        elif elapsed > 20:
            print(f"⚠️  WARNING: Fallback parse took {elapsed:.2f}s (> 20s)")
            timing_assertion = "warn_gt_20s"
        else:
            timing_assertion = "pass"

        print(f"✅ SUCCESS: Parse completed in {elapsed:.2f}s")
        print(f"   Keys present: {list(result.keys())}")

        return {
            "success": True,
            "method": "gpt4o_mini_baml",
            "elapsed_seconds": elapsed,
            "keys": list(result.keys()),
            "error": None,
            "env_state": env_state,
            "timing_assertion": timing_assertion,
        }
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ FAILED after {elapsed:.2f}s: {e}")
        return {
            "success": False,
            "method": "gpt4o_mini_baml",
            "elapsed_seconds": elapsed,
            "keys": None,
            "error": str(e),
            "env_state": env_state,
            "timing_assertion": "fail",
        }


def main():
    """Run smoke tests and generate report."""
    print("Scout BAML CLI Smoke Test")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Working directory: {os.getcwd()}")

    # Check Claude CLI availability
    print("\n" + "=" * 60)
    print("Environment Check")
    print("=" * 60)
    cli_available, cli_version = check_claude_cli_available()
    print(f"Claude CLI available: {cli_available}")
    if cli_available:
        print(f"Claude CLI version: {cli_version}")
    print(f"OPENAI_API_KEY set: {bool(os.getenv('OPENAI_API_KEY'))}")
    print(f"BAML_USE_CLAUDE_CLI default: {os.getenv('BAML_USE_CLAUDE_CLI', 'true')}")
    initial_env_state = {
        "BAML_USE_CLAUDE_CLI": os.getenv("BAML_USE_CLAUDE_CLI", "true"),
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
    }

    # Run tests
    results = []

    if cli_available:
        results.append(test_scout_parse_with_cli())
    else:
        print("\n⏭️  SKIPPING Claude CLI test: CLI not available")
        results.append(
            {
                "success": None,
                "method": "claude_cli",
                "elapsed_seconds": 0,
                "error": "Claude CLI not available",
            }
        )

    results.append(test_scout_parse_fallback())

    # Generate report
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    report = {
        "timestamp": datetime.now().isoformat(),
        "environment": {
            "claude_cli_available": cli_available,
            "claude_cli_version": cli_version,
            "openai_api_key_set": bool(os.getenv("OPENAI_API_KEY")),
            "baml_use_claude_cli": os.getenv("BAML_USE_CLAUDE_CLI", "true"),
            "initial_env_state": initial_env_state,
        },
        "tests": results,
    }

    # Save report to file
    report_path = (
        Path(__file__).parent.parent / ".context-foundry" / "scout_cli_smoke_test.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\n📄 Report saved to: {report_path}")

    # Print summary
    for result in results:
        status = (
            "✅ PASS"
            if result["success"]
            else "❌ FAIL"
            if result["success"] is False
            else "⏭️  SKIP"
        )
        print(f"{status} - {result['method']}: {result['elapsed_seconds']:.2f}s")
        if result.get("env_state"):
            print(f"         Env: {result['env_state']}")
        if result.get("timing_assertion"):
            assertion_icon = (
                "✅"
                if result["timing_assertion"] in ["pass"]
                else "⚠️"
                if result["timing_assertion"].startswith("warn")
                else "❌"
                if result["timing_assertion"] == "fail"
                else "⏭️"
            )
            print(
                f"         Timing: {assertion_icon} {result['timing_assertion']} (threshold: <30s, warn >20s)"
            )
        if result.get("error"):
            print(f"         Error: {result['error']}")

    # Exit with appropriate code
    if any(r["success"] is False for r in results):
        sys.exit(1)
    elif all(r["success"] is None for r in results):
        print("\n⚠️  All tests skipped - cannot verify fix")
        sys.exit(2)
    else:
        print("\n✅ All tests passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
