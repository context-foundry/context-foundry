"""
Relay Orchestrator
==================

Main orchestration loop for feature-by-feature autonomous building.
Implements Anthropic's pattern for long-running agents with fresh context per feature.

Supports two execution modes:
1. Claude Agent SDK (preferred) - if claude_agent_sdk is installed
2. Subprocess delegation (fallback) - uses existing CF infrastructure

Based on:
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- https://github.com/leonvanzyl/autonomous-coding
"""

import asyncio
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .feature_list import FeatureList, Feature, parse_feature_list_from_output
from .prompts import (
    get_initialization_prompt,
    get_coding_agent_prompt,
    copy_spec_to_project,
    get_system_prompt,
    format_feature_context,
)

# Try to import Claude Agent SDK
try:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    from claude_agent_sdk.types import HookMatcher

    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False
    ClaudeSDKClient = None
    ClaudeAgentOptions = None
    HookMatcher = None


# Configuration
DEFAULT_MODEL = "claude-opus-4-5-20251101"
AUTO_CONTINUE_DELAY_SECONDS = 3
PROGRESS_CACHE_FILE = ".relay_progress_cache"


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════


def send_progress_webhook(
    webhook_url: Optional[str],
    feature: Feature,
    feature_list: FeatureList,
    project_dir: Path,
    event_type: str = "feature_completed",
) -> None:
    """
    Send webhook notification for progress updates.

    Compatible with Flowise/N8N webhooks.

    Args:
        webhook_url: Webhook URL to send to (None to skip)
        feature: Feature that was completed
        feature_list: Current feature list state
        project_dir: Project directory
        event_type: Type of event (feature_completed, build_started, etc.)
    """
    if not webhook_url:
        return

    payload = {
        "event": event_type,
        "project_name": feature_list.project_name,
        "feature": {
            "id": feature.id,
            "description": feature.description,
            "category": feature.category,
            "passes": feature.passes,
        },
        "progress": {
            "completed": feature_list.completed_count,
            "total": feature_list.total_features,
            "percentage": round(feature_list.completion_percentage, 1),
        },
        "project_dir": str(project_dir),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps([payload]).encode("utf-8"),  # N8N expects array
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[Webhook notification failed: {e}]", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════════════════════
# SUBPROCESS EXECUTION (Fallback when Claude SDK not available)
# ═══════════════════════════════════════════════════════════════════════════════


def run_claude_subprocess(
    prompt: str,
    project_dir: Path,
    model: str,
    timeout_minutes: float = 30.0,
) -> tuple[str, str, int]:
    """
    Run Claude CLI as a subprocess.

    This is the fallback when Claude Agent SDK is not available.

    Args:
        prompt: The prompt to send
        project_dir: Working directory
        model: Model to use
        timeout_minutes: Timeout in minutes

    Returns:
        (stdout, stderr, exit_code)
    """
    cmd = [
        "claude",
        "--print",
        "--permission-mode",
        "bypassPermissions",
        "--model",
        model,
        prompt,
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=timeout_minutes * 60,
            env={
                **os.environ,
                "PYTHONUNBUFFERED": "1",
            },
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Session timed out", 1
    except Exception as e:
        return "", str(e), 1


# ═══════════════════════════════════════════════════════════════════════════════
# CLAUDE SDK EXECUTION (Preferred)
# ═══════════════════════════════════════════════════════════════════════════════


def create_sdk_client(project_dir: Path, model: str) -> Optional["ClaudeSDKClient"]:
    """
    Create a Claude Agent SDK client with security settings.

    Args:
        project_dir: Project directory
        model: Model to use

    Returns:
        ClaudeSDKClient or None if SDK not available
    """
    if not CLAUDE_SDK_AVAILABLE:
        return None

    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    oauth_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if not api_key and not oauth_token:
        print(
            "Warning: No Claude auth configured. Set ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN",
            file=sys.stderr,
        )
        return None

    # Create security settings
    security_settings = {
        "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True},
        "permissions": {
            "defaultMode": "acceptEdits",
            "allow": [
                "Read(./**)",
                "Write(./**)",
                "Edit(./**)",
                "Glob(./**)",
                "Grep(./**)",
                "Bash(*)",
            ],
        },
    }

    # Write settings file
    settings_file = project_dir / ".relay_settings.json"
    settings_file.write_text(json.dumps(security_settings, indent=2))

    return ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model=model,
            system_prompt=get_system_prompt(),
            allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
            max_turns=1000,
            cwd=str(project_dir.resolve()),
            settings=str(settings_file.resolve()),
        )
    )


async def run_sdk_session(
    client: "ClaudeSDKClient",
    prompt: str,
    project_dir: Path,
) -> tuple[str, str]:
    """
    Run a session using Claude Agent SDK.

    Args:
        client: SDK client
        prompt: Prompt to send
        project_dir: Project directory

    Returns:
        (status, response_text) where status is "continue" or "error"
    """
    print("Sending prompt to Claude Agent SDK...\n", file=sys.stderr)

    try:
        await client.query(prompt)

        response_text = ""
        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "TextBlock" and hasattr(block, "text"):
                        response_text += block.text
                        print(block.text, end="", flush=True)
                    elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                        print(f"\n[Tool: {block.name}]", flush=True)

        print("\n" + "-" * 70 + "\n", file=sys.stderr)
        return "continue", response_text

    except Exception as e:
        print(f"Error during agent session: {e}", file=sys.stderr)
        return "error", str(e)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════


async def run_initialization_session(
    project_dir: Path,
    model: str,
    task: str,
    feature_count: int,
) -> Optional[FeatureList]:
    """
    Run the initialization agent to create feature list.

    Args:
        project_dir: Project directory
        model: Model to use
        task: Task description
        feature_count: Target number of features

    Returns:
        FeatureList if successful, None otherwise
    """
    # Create app_spec.txt from task
    copy_spec_to_project(project_dir, task)

    # Get initialization prompt
    prompt = get_initialization_prompt(feature_count)

    print("\n" + "=" * 70, file=sys.stderr)
    print("  RELAY: INITIALIZATION SESSION", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"\nGenerating {feature_count} features...", file=sys.stderr)
    print("This may take 10-20+ minutes.\n", file=sys.stderr)

    # Try SDK first, fall back to subprocess
    if CLAUDE_SDK_AVAILABLE:
        client = create_sdk_client(project_dir, model)
        if client:
            async with client:
                status, response = await run_sdk_session(client, prompt, project_dir)
        else:
            stdout, stderr, _ = run_claude_subprocess(prompt, project_dir, model, 30)
            response = stdout
    else:
        stdout, stderr, _ = run_claude_subprocess(prompt, project_dir, model, 30)
        response = stdout

    # Check if feature_list.json was created
    feature_list_path = FeatureList.get_path(project_dir)
    if not feature_list_path.exists():
        # Also check project root
        alt_path = project_dir / "feature_list.json"
        if alt_path.exists():
            feature_list_path = alt_path

    if feature_list_path.exists():
        return FeatureList.load(feature_list_path)

    # Try to parse from output
    project_name = project_dir.name
    return parse_feature_list_from_output(response, project_name)


async def run_coding_session(
    project_dir: Path,
    model: str,
    feature: Feature,
    regression_features: List[Feature],
) -> tuple[str, str]:
    """
    Run a coding agent session for one feature.

    Args:
        project_dir: Project directory
        model: Model to use
        feature: Feature to implement
        regression_features: Features to regression test first

    Returns:
        (status, response) tuple
    """
    # Format context for this feature
    context = format_feature_context(
        feature.id,
        feature.description,
        feature.acceptance_criteria,
        [{"id": f.id, "description": f.description} for f in regression_features],
    )

    # Get coding prompt
    prompt = context + get_coding_agent_prompt()

    print(f"\n[Feature: {feature.id}] {feature.description[:60]}...", file=sys.stderr)

    # Try SDK first, fall back to subprocess
    if CLAUDE_SDK_AVAILABLE:
        client = create_sdk_client(project_dir, model)
        if client:
            async with client:
                return await run_sdk_session(client, prompt, project_dir)

    stdout, stderr, exit_code = run_claude_subprocess(prompt, project_dir, model, 15)
    status = "continue" if exit_code == 0 else "error"
    return status, stdout


async def relay_build_async(
    task: str,
    working_directory: str,
    feature_count: int = 50,
    max_iterations: int = 200,
    regression_sample_size: int = 2,
    timeout_per_feature: float = 10.0,
    model: str = DEFAULT_MODEL,
    webhook_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main Relay build function (async).

    Args:
        task: Project description/requirements
        working_directory: Where to create the project
        feature_count: Target number of features
        max_iterations: Maximum iterations (safety limit)
        regression_sample_size: Features to regression test
        timeout_per_feature: Minutes per feature
        model: Model for coding agents
        webhook_url: Webhook for progress notifications

    Returns:
        Build results dictionary
    """
    project_dir = Path(working_directory)
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create .relay directory
    relay_dir = project_dir / ".relay"
    relay_dir.mkdir(exist_ok=True)

    start_time = datetime.now()
    results = {
        "status": "running",
        "project_dir": str(project_dir),
        "model": model,
        "start_time": start_time.isoformat(),
        "iterations": 0,
        "features_completed": 0,
        "features_total": 0,
    }

    # Check if continuing existing project
    feature_list_path = FeatureList.get_path(project_dir)
    alt_path = project_dir / "feature_list.json"

    if feature_list_path.exists():
        feature_list = FeatureList.load(feature_list_path)
        print(
            f"\nContinuing existing project: {feature_list.get_progress_summary()}",
            file=sys.stderr,
        )
    elif alt_path.exists():
        feature_list = FeatureList.load(alt_path)
        print(
            f"\nContinuing existing project: {feature_list.get_progress_summary()}",
            file=sys.stderr,
        )
    else:
        # Run initialization
        feature_list = await run_initialization_session(
            project_dir, model, task, feature_count
        )
        if not feature_list:
            results["status"] = "failed"
            results["error"] = "Failed to generate feature list"
            return results

        # Save to .relay directory
        feature_list.save(feature_list_path)

    results["features_total"] = feature_list.total_features

    # Main feature loop
    iteration = 0
    while not feature_list.is_complete and iteration < max_iterations:
        iteration += 1
        results["iterations"] = iteration

        # Get next feature
        feature = feature_list.get_next_feature()
        if not feature:
            break

        print(f"\n{'=' * 70}", file=sys.stderr)
        print(f"  RELAY SESSION {iteration}: {feature.id}", file=sys.stderr)
        print(f"{'=' * 70}", file=sys.stderr)

        # Get regression test targets
        regression_features = feature_list.get_random_completed_features(
            regression_sample_size
        )

        # Run coding session
        status, response = await run_coding_session(
            project_dir, model, feature, regression_features
        )

        # Check if feature was completed (look for updated feature_list.json)
        try:
            updated_list = FeatureList.load(feature_list_path)
            if updated_list.get_feature_by_id(feature.id).passes:
                feature_list = updated_list
                results["features_completed"] = feature_list.completed_count

                # Send webhook
                send_progress_webhook(webhook_url, feature, feature_list, project_dir)

                print(f"\n{feature_list.get_progress_summary()}", file=sys.stderr)
        except Exception:
            # Feature list might be in alt location
            if alt_path.exists():
                try:
                    updated_list = FeatureList.load(alt_path)
                    feature_list = updated_list
                    feature_list.save(feature_list_path)  # Normalize location
                except Exception:
                    pass

        # Delay between sessions
        if not feature_list.is_complete:
            print(
                f"\nAuto-continuing in {AUTO_CONTINUE_DELAY_SECONDS}s...",
                file=sys.stderr,
            )
            await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

    # Final results
    duration = (datetime.now() - start_time).total_seconds()
    results["status"] = "completed" if feature_list.is_complete else "partial"
    results["end_time"] = datetime.now().isoformat()
    results["duration_seconds"] = duration
    results["features_completed"] = feature_list.completed_count
    results["completion_percentage"] = feature_list.completion_percentage

    print("\n" + "=" * 70, file=sys.stderr)
    print("  RELAY BUILD COMPLETE", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"\n{feature_list.get_progress_summary()}", file=sys.stderr)
    print(f"Duration: {duration:.1f}s", file=sys.stderr)

    return results


def relay_build_impl(
    task: str,
    working_directory: str,
    feature_count: int = 50,
    max_iterations: int = 200,
    regression_sample_size: int = 2,
    timeout_per_feature: float = 10.0,
    model: str = DEFAULT_MODEL,
    webhook_url: Optional[str] = None,
) -> str:
    """
    Main Relay build function (sync wrapper for MCP).

    This is the entry point called by the MCP tool.

    Args:
        task: Project description/requirements
        working_directory: Where to create the project
        feature_count: Target number of features
        max_iterations: Maximum iterations (safety limit)
        regression_sample_size: Features to regression test
        timeout_per_feature: Minutes per feature
        model: Model for coding agents
        webhook_url: Webhook for progress notifications

    Returns:
        JSON string with build results
    """
    # Check for nested event loop
    try:
        asyncio.get_running_loop()
        # We're in an async context, need nest_asyncio
        import nest_asyncio

        nest_asyncio.apply()
    except RuntimeError:
        pass  # No running loop, we're fine

    result = asyncio.run(
        relay_build_async(
            task=task,
            working_directory=working_directory,
            feature_count=feature_count,
            max_iterations=max_iterations,
            regression_sample_size=regression_sample_size,
            timeout_per_feature=timeout_per_feature,
            model=model,
            webhook_url=webhook_url,
        )
    )

    return json.dumps(result, indent=2)
