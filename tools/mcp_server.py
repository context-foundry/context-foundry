#!/usr/bin/env python3
"""
MCP Server for Context Foundry
Enables Claude Desktop to use Context Foundry without API charges
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add parent directory to path for imports (must be before local imports!)
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import version management (single source of truth)
from tools.version import get_version

# Import BAML integration for type-safe phase tracking

# Import safety mechanisms for sandbox enforcement

# Check if FastMCP is available
try:
    from fastmcp import FastMCP, Context  # noqa: F401
    from fastmcp.server.dependencies import get_context  # noqa: F401
except ImportError:
    print("❌ Error: FastMCP not installed", file=sys.stderr)
    print("", file=sys.stderr)
    print(
        "MCP Server mode requires Python 3.10+ and the fastmcp package.",
        file=sys.stderr,
    )
    print("", file=sys.stderr)
    print("To install MCP mode dependencies:", file=sys.stderr)
    print("  1. Upgrade to Python 3.10 or higher", file=sys.stderr)
    print("  2. Run: pip install -r requirements-mcp.txt", file=sys.stderr)
    print("", file=sys.stderr)
    print("Or use API mode instead (no Python version requirement):", file=sys.stderr)
    print("  export ANTHROPIC_API_KEY=your_key", file=sys.stderr)
    print("  foundry build my-app 'task description'", file=sys.stderr)
    print("", file=sys.stderr)
    sys.exit(1)

from tools.banner import print_banner

# Import modularized utilities (Phase 2 refactoring - Phases 1-5 complete)
# These maintain backward compatibility via re-exports below
from tools.mcp.output_utils import truncate_output, create_output_summary
from tools.mcp.phase_tracking import read_phase_info
from tools.mcp.path_utils import get_context_foundry_parent_dir
from tools.mcp.project_detection import detect_existing_codebase
from tools.mcp.task_classification import detect_task_intent
from tools.mcp.pattern_management import (
    read_global_patterns_impl,
    save_global_patterns_impl,
    merge_project_patterns_impl,
)
from tools.mcp.delegation import (
    delegate_to_claude_code_impl,
    delegate_to_claude_code_async_impl,
    get_delegation_result_impl,
    list_delegations_impl,
    cancel_delegation_impl,
    stream_delegation_output_impl,
)
from tools.mcp.autonomous_build import autonomous_build_and_deploy_impl

# Re-export with underscore-prefixed names for backward compatibility
# Tests and external code may import these directly
_truncate_output = truncate_output
_create_output_summary = create_output_summary
_read_phase_info = read_phase_info
_get_context_foundry_parent_dir = get_context_foundry_parent_dir
_detect_existing_codebase = detect_existing_codebase
_detect_task_intent = detect_task_intent
_read_global_patterns_impl = read_global_patterns_impl
_save_global_patterns_impl = save_global_patterns_impl
_merge_project_patterns_impl = merge_project_patterns_impl
_delegate_to_claude_code_impl = delegate_to_claude_code_impl
_delegate_to_claude_code_async_impl = delegate_to_claude_code_async_impl
_get_delegation_result_impl = get_delegation_result_impl
_list_delegations_impl = list_delegations_impl
_cancel_delegation_impl = cancel_delegation_impl
_stream_delegation_output_impl = stream_delegation_output_impl
_autonomous_build_and_deploy_impl = autonomous_build_and_deploy_impl

# Create MCP server
mcp = FastMCP("Context Foundry")

# Track active builds
active_builds = {}

# Track async delegation tasks
# Structure: {task_id: {process, cmd, cwd, start_time, status, result, stdout, stderr, duration}}
active_tasks: Dict[str, Dict[str, Any]] = {}


# ANCHOR: read_phase_info
# Moved to tools/mcp/phase_tracking.py - imported above with re-export as _read_phase_info

# ANCHOR: get_context_foundry_parent_dir
# Moved to tools/mcp/path_utils.py - imported above with re-export as _get_context_foundry_parent_dir

# ANCHOR: truncate_output
# Moved to tools/mcp/output_utils.py - imported above with re-export as _truncate_output

# ANCHOR: write_delegation_metadata
# Moved to tools/mcp/delegation.py - imported above

# ANCHOR: write_full_output_to_file
# Moved to tools/mcp/delegation.py - imported above


# ANCHOR: create_output_summary
# Moved to tools/mcp/output_utils.py - imported above with re-export as _create_output_summary


# ANCHOR: context_foundry_status
@mcp.tool()
def context_foundry_status() -> str:
    """
    Get the current status of Context Foundry.

    Returns:
        Status information including version and capabilities
    """
    return f"""Context Foundry - Status

✅ Running
✅ Version: {get_version()}

**Quick Commands - Just Say:**

🚀 **Build & Deploy:**
- "Build a <description> app"
- "Create a <type> application"
- "Deploy my app to GitHub"
- "Start a new project for <purpose>"

🔧 **Fix & Enhance:**
- "Fix the <issue> in my app"
- "Add <feature> to my project"
- "Extend my app with <functionality>"
- "Improve <aspect> of my code"
- "Debug the <problem>"

📦 **Manage:**
- "Show my active builds"
- "Cancel this build"
- "Check build status"
- "List my projects"

**How to Use:**
Just describe what you want in plain English. Context Foundry handles the rest.
No commands to memorize, no syntax to learn.
"""


# ANCHOR: delegate_to_claude_code
# Moved to tools/mcp/delegation.py
@mcp.tool()
def delegate_to_claude_code(
    task: str,
    working_directory: Optional[str] = None,
    timeout_minutes: float = 10.0,
    additional_flags: Optional[str] = None,
    include_full_output: bool = False,
) -> str:
    """
    Delegate a task to a fresh Claude Code CLI instance.

    Spawns a new claude-code process, passes it the task, waits for completion,
    and returns the output. This allows the current Claude Code session to delegate
    work to fresh instances with clean context.

    Args:
        task: The task/prompt to give to the new Claude Code instance
        working_directory: Directory where claude-code should run (defaults to current directory)
        timeout_minutes: Maximum execution time in minutes (default: 10 minutes)
        additional_flags: Additional CLI flags as a string (e.g., "--model claude-sonnet-4")
        include_full_output: If False (default), truncate large outputs to stay under token limits.
                            If True, return complete stdout/stderr regardless of size.

    Returns:
        Formatted output with status, duration, stdout, and stderr (truncated if needed)

    Examples:
        # Simple task delegation
        delegate_to_claude_code("Create a hello.py file that prints 'Hello World'")

        # With working directory
        delegate_to_claude_code(
            task="Run all tests and report results",
            working_directory="/path/to/project"
        )

        # With timeout and custom flags
        delegate_to_claude_code(
            task="Analyze this codebase and create documentation",
            timeout_minutes=20.0,
            additional_flags="--model claude-sonnet-4"
        )
    """
    return delegate_to_claude_code_impl(
        task=task,
        working_directory=working_directory,
        timeout_minutes=timeout_minutes,
        additional_flags=additional_flags,
        include_full_output=include_full_output,
        truncate_output_func=_truncate_output,
    )


# ANCHOR: delegate_to_claude_code_async
# Moved to tools/mcp/delegation.py
@mcp.tool()
def delegate_to_claude_code_async(
    task: str,
    working_directory: Optional[str] = None,
    timeout_minutes: float = 10.0,
    additional_flags: Optional[str] = None,
) -> str:
    """
    Delegate a task to a fresh Claude Code CLI instance asynchronously (runs in background).

    This starts the task immediately and returns a task ID. The task runs in the background
    while you continue working. Use get_delegation_result() to check status and retrieve results.

    Args:
        task: The task/prompt to give to the new Claude Code instance
        working_directory: Directory where claude should run (defaults to current directory)
        timeout_minutes: Maximum execution time in minutes (default: 10 minutes)
        additional_flags: Additional CLI flags as a string (e.g., "--model claude-sonnet-4")

    Returns:
        JSON string with task_id and status

    Examples:
        # Start 3 tasks in parallel
        task1 = delegate_to_claude_code_async("Analyze codebase architecture")
        task2 = delegate_to_claude_code_async("Write comprehensive tests")
        task3 = delegate_to_claude_code_async("Generate API documentation")

        # All 3 run simultaneously! Check results later with get_delegation_result(task_id)
    """
    return delegate_to_claude_code_async_impl(
        task=task,
        working_directory=working_directory,
        timeout_minutes=timeout_minutes,
        additional_flags=additional_flags,
        active_tasks=active_tasks,
    )


# ANCHOR: get_delegation_result
# Moved to tools/mcp/delegation.py
@mcp.tool()
def get_delegation_result(task_id: str, include_full_output: bool = False) -> str:
    """
    Get the status and results of an async delegation task.

    Args:
        task_id: The task ID returned from delegate_to_claude_code_async()
        include_full_output: If False (default), return smart summary (first 50 + last 50 lines).
                            If True, return complete stdout/stderr (may exceed MCP token limits).

    Returns:
        JSON string with task status and results:
        - If running: Shows elapsed time and phase progress
        - If complete (summary mode): Shows first 50 + last 50 lines of output
        - If complete (full mode): Shows complete output (may exceed 25K token limit)
        - Full output always saved to .context-foundry/build-output-{task_id}.txt

    Examples:
        # Check task status (default: smart summary)
        result = get_delegation_result("abc-123-def-456")
        # Returns: stdout_summary, stderr_summary, output_file path

        # Get full output (warning: may exceed MCP 25K token limit)
        result = get_delegation_result("abc-123-def-456", include_full_output=True)

        # Read full output from file instead (recommended for large builds)
        # Check result["output_file"] and use Read tool to view complete output
    """
    return get_delegation_result_impl(
        task_id=task_id,
        include_full_output=include_full_output,
        active_tasks=active_tasks,
        read_phase_info_func=_read_phase_info,
        create_output_summary_func=_create_output_summary,
        merge_project_patterns_func=merge_project_patterns,
    )


# ANCHOR: list_delegations
# Moved to tools/mcp/delegation.py
@mcp.tool()
def list_delegations() -> str:
    """
    List all async delegation tasks (both running and completed).

    Returns:
        JSON string with list of all tasks and their status

    Examples:
        # See all tasks
        tasks = list_delegations()

        # Shows task IDs, status, elapsed time, etc.
    """
    return list_delegations_impl(active_tasks=active_tasks)


# ANCHOR: cancel_delegation
# Moved to tools/mcp/delegation.py
@mcp.tool()
def cancel_delegation(task_id: str, reason: Optional[str] = None) -> str:
    """
    Manually cancel/kill a running delegation task.

    This allows you to stop a runaway build, unwanted task, or process that's
    taking too long. The process will be terminated gracefully if possible,
    or killed forcefully if needed.

    Args:
        task_id: The task ID to cancel (from delegate_to_claude_code_async or autonomous_build_and_deploy)
        reason: Optional reason for cancellation (for logging/debugging)

    Returns:
        JSON string with cancellation status and details

    Examples:
        # Cancel a runaway build
        result = cancel_delegation("abc-123-def-456", "Taking too long")

        # Cancel without reason
        result = cancel_delegation("abc-123-def-456")
    """
    return cancel_delegation_impl(
        task_id=task_id,
        reason=reason,
        active_tasks=active_tasks,
    )


# ANCHOR: stream_delegation_output
# Moved to tools/mcp/delegation.py
@mcp.tool()
def stream_delegation_output(
    task_id: str,
    lines: int = 50,
    include_phase_info: bool = True,
    filter_pattern: Optional[str] = None,
) -> str:
    """
    Stream raw, real-time output from a running or completed delegation task.

    This shows the UGLY, UNFILTERED stream of what's happening:
    - Raw stdout/stderr from the claude process
    - LLM responses and tool calls
    - Phase transitions (if include_phase_info=True)
    - Agent switches and orchestrator decisions
    - Errors and warnings as they happen

    This is a diagnostic tool - the output may be hard to read but shows
    exactly what's happening in real-time.

    Args:
        task_id: The task ID to stream output from
        lines: Number of recent lines to show (default: 50, like tail -n 50)
        include_phase_info: Whether to prepend current phase information (default: True)
        filter_pattern: Optional regex pattern to filter lines (only matching lines shown)

    Returns:
        JSON string with streaming output and metadata

    Examples:
        # Show last 50 lines of output
        stream = stream_delegation_output("abc-123-def-456")

        # Show last 100 lines
        stream = stream_delegation_output("abc-123-def-456", lines=100)

        # Filter for errors only
        stream = stream_delegation_output("abc-123-def-456", filter_pattern="error|ERROR|failed")

        # Just raw output, no phase info
        stream = stream_delegation_output("abc-123-def-456", include_phase_info=False)
    """
    return stream_delegation_output_impl(
        task_id=task_id,
        lines=lines,
        include_phase_info=include_phase_info,
        filter_pattern=filter_pattern,
        active_tasks=active_tasks,
        read_phase_info_func=_read_phase_info,
    )


# ANCHOR: detect_existing_codebase
# Moved to tools/mcp/project_detection.py - imported above with re-export as _detect_existing_codebase

# ANCHOR: detect_task_intent
# Moved to tools/mcp/task_classification.py - imported above with re-export as _detect_task_intent


def _autonomous_build_and_deploy_impl(
    task: str,
    working_directory: str,
    github_repo_name: Optional[str] = None,
    existing_repo: Optional[str] = None,
    mode: str = "new_project",
    enable_test_loop: bool = True,
    max_test_iterations: int = 3,
    timeout_minutes: float = 90.0,
    use_parallel: bool = False,
    incremental: bool = False,
    force_rebuild: bool = False,
    sandbox_path: Optional[str] = None,
    sandbox_task_id: Optional[str] = None,
) -> str:
    """Internal implementation of autonomous_build_and_deploy (not decorated)"""
    # ANCHOR: autonomous_build_and_deploy_impl
    # Moved to tools/mcp/autonomous_build.py - imported above with re-export as _autonomous_build_and_deploy_impl
    return autonomous_build_and_deploy_impl(
        task=task,
        working_directory=working_directory,
        github_repo_name=github_repo_name,
        existing_repo=existing_repo,
        mode=mode,
        enable_test_loop=enable_test_loop,
        max_test_iterations=max_test_iterations,
        timeout_minutes=timeout_minutes,
        use_parallel=use_parallel,
        incremental=incremental,
        force_rebuild=force_rebuild,
        sandbox_path=sandbox_path,
        sandbox_task_id=sandbox_task_id,
        active_tasks=active_tasks,
    )


# MCP tool wrapper (calls the implementation function above)
@mcp.tool()
def autonomous_build_and_deploy(
    task: str,
    working_directory: str,
    github_repo_name: Optional[str] = None,
    existing_repo: Optional[str] = None,
    mode: str = "new_project",
    enable_test_loop: bool = True,
    max_test_iterations: int = 3,
    timeout_minutes: float = 90.0,
    use_parallel: bool = False,
    incremental: bool = False,
    force_rebuild: bool = False,
) -> str:
    """
    MCP tool wrapper for autonomous_build_and_deploy.

    Delegates to the internal implementation function.
    """
    return _autonomous_build_and_deploy_impl(
        task=task,
        working_directory=working_directory,
        github_repo_name=github_repo_name,
        existing_repo=existing_repo,
        mode=mode,
        enable_test_loop=enable_test_loop,
        max_test_iterations=max_test_iterations,
        timeout_minutes=timeout_minutes,
        use_parallel=use_parallel,
        incremental=incremental,
        force_rebuild=force_rebuild,
    )


# ============================================================================
# Global Pattern Sharing Functions
# ============================================================================


# ============================================================================
# Internal Pattern Storage Implementations (callable from Python)
# ============================================================================


def _read_global_patterns_impl(pattern_type: str = "common-issues") -> dict:
    # ANCHOR: read_global_patterns
    # Moved to tools/mcp/pattern_management.py - imported above with re-export as _read_global_patterns_impl
    return read_global_patterns_impl(pattern_type)


def _save_global_patterns_impl(pattern_type: str, data: dict) -> dict:
    # ANCHOR: save_global_patterns
    # Moved to tools/mcp/pattern_management.py - imported above with re-export as _save_global_patterns_impl
    return save_global_patterns_impl(pattern_type, data)


def _merge_project_patterns_impl(
    project_pattern_file: str,
    pattern_type: str = "common-issues",
    increment_build_count: bool = True,
) -> dict:
    # ANCHOR: merge_project_patterns
    # Moved to tools/mcp/pattern_management.py - imported above with re-export as _merge_project_patterns_impl
    return merge_project_patterns_impl(
        project_pattern_file, pattern_type, increment_build_count
    )


# ============================================================================
# MCP Tool Wrappers (external interface)
# ============================================================================


@mcp.tool()
def read_global_patterns(pattern_type: str = "common-issues") -> str:
    """
    Read global patterns from ~/.context-foundry/patterns/

    Args:
        pattern_type: Type of patterns to read ("common-issues", "scout-learnings", "build-metrics",
                     "architecture-patterns", "test-patterns", "mcp-server-patterns")

    Returns:
        JSON string with patterns or error message

    Examples:
        # Read common issues
        patterns = read_global_patterns("common-issues")

        # Read scout learnings
        learnings = read_global_patterns("scout-learnings")

        # Read MCP server patterns
        mcp_patterns = read_global_patterns("mcp-server-patterns")
    """
    result = _read_global_patterns_impl(pattern_type)

    # For MCP tool interface, return just the data if successful, otherwise return the error
    if result.get("status") == "success":
        return json.dumps(result["data"], indent=2)
    else:
        return json.dumps(result, indent=2)


@mcp.tool()
def save_global_patterns(pattern_type: str, patterns_data: str) -> str:
    """
    Save patterns to global pattern storage.

    Args:
        pattern_type: Type of patterns ("common-issues", "scout-learnings", "build-metrics")
        patterns_data: JSON string containing the patterns data

    Returns:
        JSON string with save result

    Examples:
        # Save common issues
        data = json.dumps({"patterns": [...], "version": "1.0", ...})
        result = save_global_patterns("common-issues", data)
    """
    try:
        # Parse patterns data
        data = json.loads(patterns_data)
    except json.JSONDecodeError as e:
        return json.dumps(
            {"status": "error", "error": f"Invalid JSON in patterns_data: {str(e)}"},
            indent=2,
        )

    # Call internal implementation
    result = _save_global_patterns_impl(pattern_type, data)
    return json.dumps(result, indent=2)


@mcp.tool()
def merge_project_patterns(
    project_pattern_file: str = None,  # New parameter name
    pattern_type: str = "common-issues",
    increment_build_count: bool = True,
    project_path: str = None,  # Legacy parameter for backward compatibility
    conflict_resolution: str = None,  # Legacy parameter (not implemented, for test compatibility)
) -> str:
    """
    Merge patterns from a project-specific file into global pattern storage.

    This implements the pattern merge logic:
    - New patterns are added
    - Existing patterns have frequency incremented and last_seen updated
    - Project types are merged
    - Highest severity is preserved

    Args:
        project_pattern_file: Path to project-specific pattern file
        pattern_type: Type of patterns ("common-issues", "scout-learnings")
        increment_build_count: Whether to increment total_builds counter

    Returns:
        JSON string with merge results

    Examples:
        # Merge common issues from a project
        result = merge_project_patterns(
            "/Users/name/homelab/my-app/.context-foundry/patterns/common-issues.json",
            "common-issues"
        )
    """
    # Handle backward compatibility: accept both project_pattern_file and project_path
    file_path = project_pattern_file or project_path
    if not file_path:
        return json.dumps(
            {
                "status": "error",
                "error": "Either project_pattern_file or project_path must be provided",
            },
            indent=2,
        )

    # Call internal implementation
    result = _merge_project_patterns_impl(
        file_path, pattern_type, increment_build_count
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def migrate_all_project_patterns(
    projects_base_dir: str = None,
    projects_dir: str = None,  # Support both names
) -> str:
    """
    Migrate patterns from all projects in a directory to global storage.

    Scans all subdirectories for .context-foundry/patterns/ and merges them.

    Args:
        projects_base_dir: Base directory containing project subdirectories

    Returns:
        JSON string with migration results

    Examples:
        # Migrate all projects in homelab
        result = migrate_all_project_patterns("/Users/name/homelab")
    """
    # Handle backward compatibility
    base_dir = projects_base_dir or projects_dir
    if not base_dir:
        return json.dumps(
            {
                "status": "error",
                "error": "Either projects_base_dir or projects_dir must be provided",
            },
            indent=2,
        )

    try:
        base_path = Path(base_dir)
        if not base_path.exists():
            return json.dumps(
                {
                    "status": "error",
                    "error": f"Directory not found: {base_dir}",
                },
                indent=2,
            )

        # Find all project pattern directories
        pattern_dirs = []
        for project_dir in base_path.iterdir():
            if project_dir.is_dir():
                pattern_dir = project_dir / ".context-foundry" / "patterns"
                if pattern_dir.exists():
                    pattern_dirs.append(
                        {"project": project_dir.name, "path": pattern_dir}
                    )

        if not pattern_dirs:
            return json.dumps(
                {
                    "status": "success",
                    "message": "No project patterns found to migrate",
                    "projects_scanned": len(list(base_path.iterdir())),
                },
                indent=2,
            )

        # Migrate each project
        migration_results = {
            "projects_migrated": 0,
            "total_patterns_merged": 0,
            "errors": [],
        }

        for proj_info in pattern_dirs:
            project_name = proj_info["project"]
            pattern_dir = proj_info["path"]

            # Migrate common-issues.json if it exists
            common_issues_file = pattern_dir / "common-issues.json"
            if common_issues_file.exists():
                result_data = _merge_project_patterns_impl(
                    str(common_issues_file),
                    "common-issues",
                    increment_build_count=False,  # Don't increment for migration
                )
                if result_data["status"] == "success":
                    migration_results["total_patterns_merged"] += result_data[
                        "merge_stats"
                    ]["new_patterns"]
                    migration_results["total_patterns_merged"] += result_data[
                        "merge_stats"
                    ]["updated_patterns"]
                else:
                    migration_results["errors"].append(
                        {
                            "project": project_name,
                            "file": "common-issues.json",
                            "error": result_data.get("error", "Unknown error"),
                        }
                    )

            # Migrate scout-learnings.json if it exists
            scout_learnings_file = pattern_dir / "scout-learnings.json"
            if scout_learnings_file.exists():
                result_data = _merge_project_patterns_impl(
                    str(scout_learnings_file),
                    "scout-learnings",
                    increment_build_count=False,
                )
                if result_data["status"] == "success":
                    migration_results["total_patterns_merged"] += result_data[
                        "merge_stats"
                    ]["new_patterns"]
                    migration_results["total_patterns_merged"] += result_data[
                        "merge_stats"
                    ]["updated_patterns"]
                else:
                    migration_results["errors"].append(
                        {
                            "project": project_name,
                            "file": "scout-learnings.json",
                            "error": result_data.get("error", "Unknown error"),
                        }
                    )

            migration_results["projects_migrated"] += 1

        return json.dumps(
            {
                "status": "success",
                "message": f"Migrated patterns from {migration_results['projects_migrated']} projects",
                "migration_results": migration_results,
                "projects_found": len(pattern_dirs),
            },
            indent=2,
        )

    except Exception as e:
        import traceback

        return json.dumps(
            {"status": "error", "error": str(e), "traceback": traceback.format_exc()},
            indent=2,
        )


@mcp.tool()
def share_patterns_to_community(
    auto_confirm: bool = True,
    skip_if_no_changes: bool = True,
    project_path: str = None,  # Legacy parameter for test compatibility
    pattern_ids: list = None,  # Legacy parameter for test compatibility
    description: str = None,  # Legacy parameter for test compatibility
) -> str:
    """
    Automatically share locally-learned patterns with the Context Foundry community.

    This creates a PR with your patterns which will be automatically validated and merged.
    Runs after successful builds to contribute learnings back to the community.

    Args:
        auto_confirm: If True, automatically confirms sharing without prompting (default: True)
        skip_if_no_changes: If True, skips sharing if no new patterns since last share (default: True)

    Returns:
        JSON string with share result

    Examples:
        # Share patterns automatically (typical use after build)
        result = share_patterns_to_community()

        # Force share even if no changes
        result = share_patterns_to_community(skip_if_no_changes=False)
    """
    try:
        import subprocess
        from datetime import datetime

        # Legacy parameter validation (for backward compatibility)
        # Validate pattern_ids before proceeding to gh auth check
        if pattern_ids is not None:
            if not project_path:
                return json.dumps(
                    {
                        "status": "error",
                        "error": "project_path required when pattern_ids is provided",
                        "shared": False,
                    },
                    indent=2,
                )

            # Load patterns from project
            project_patterns_dir = Path(project_path) / ".context-foundry" / "patterns"
            if not project_patterns_dir.exists():
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"Pattern directory not found: {project_patterns_dir}",
                        "shared": False,
                    },
                    indent=2,
                )

            # Load all pattern files to check if pattern_ids exist
            all_pattern_ids = set()
            for pattern_file in project_patterns_dir.glob("*.json"):
                try:
                    with open(pattern_file, "r") as f:
                        pattern_data = json.load(f)
                        # Check for patterns array
                        if "patterns" in pattern_data:
                            for pattern in pattern_data["patterns"]:
                                pid = pattern.get("id") or pattern.get("pattern_id")
                                if pid:
                                    all_pattern_ids.add(pid)
                except Exception:
                    continue

            # Verify all requested pattern_ids exist
            missing_ids = [pid for pid in pattern_ids if pid not in all_pattern_ids]
            if missing_ids:
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"Pattern IDs not found: {', '.join(missing_ids)}",
                        "missing_ids": missing_ids,
                        "shared": False,
                    },
                    indent=2,
                )

        # Get repository root
        repo_root = Path(__file__).parent.parent
        share_script = repo_root / "scripts" / "share-my-patterns.sh"

        if not share_script.exists():
            return json.dumps(
                {
                    "status": "error",
                    "error": f"Pattern sharing script not found: {share_script}",
                    "shared": False,
                },
                indent=2,
            )

        # Check if gh CLI is available and authenticated
        try:
            result = subprocess.run(
                ["gh", "auth", "status"], capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return json.dumps(
                    {
                        "status": "skipped",
                        "reason": "GitHub CLI not authenticated",
                        "message": "Run 'gh auth login' to enable automatic pattern sharing",
                        "shared": False,
                        "setup_instructions": "https://cli.github.com/manual/gh_auth_login",
                    },
                    indent=2,
                )
        except FileNotFoundError:
            return json.dumps(
                {
                    "status": "skipped",
                    "reason": "GitHub CLI not installed",
                    "message": "Install gh CLI to enable automatic pattern sharing",
                    "shared": False,
                    "setup_instructions": "https://cli.github.com/",
                },
                indent=2,
            )
        except subprocess.TimeoutExpired:
            return json.dumps(
                {
                    "status": "error",
                    "error": "gh auth status check timed out",
                    "shared": False,
                },
                indent=2,
            )

        # Check if local patterns exist
        local_patterns_dir = Path.home() / ".context-foundry" / "patterns"
        if not local_patterns_dir.exists():
            return json.dumps(
                {
                    "status": "skipped",
                    "reason": "No local patterns found",
                    "message": "No patterns to share yet",
                    "shared": False,
                },
                indent=2,
            )

        # Count pattern files
        pattern_files = list(local_patterns_dir.glob("*.json"))
        if not pattern_files:
            return json.dumps(
                {
                    "status": "skipped",
                    "reason": "No pattern files found",
                    "message": "No patterns to share yet",
                    "shared": False,
                },
                indent=2,
            )

        # Check if there are changes since last share (if skip_if_no_changes=True)
        if skip_if_no_changes:
            # Check if .last-pattern-share file exists
            last_share_file = local_patterns_dir / ".last-pattern-share"
            if last_share_file.exists():
                last_share_time = datetime.fromtimestamp(
                    last_share_file.stat().st_mtime
                )

                # Check if any pattern files were modified after last share
                any_newer = False
                for pf in pattern_files:
                    if datetime.fromtimestamp(pf.stat().st_mtime) > last_share_time:
                        any_newer = True
                        break

                if not any_newer:
                    return json.dumps(
                        {
                            "status": "skipped",
                            "reason": "No new patterns since last share",
                            "message": f"Last shared: {last_share_time.isoformat()}",
                            "shared": False,
                        },
                        indent=2,
                    )

        # Run the share script with auto-confirmation
        print("\n🔄 Automatically sharing patterns to community...", file=sys.stderr)

        # Prepare environment with auto-confirm
        env = os.environ.copy()
        if auto_confirm:
            # The script will need to be modified to support auto-confirm env var
            # For now, we'll use 'yes' to pipe confirmation
            process = subprocess.Popen(
                ["bash", str(share_script)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(repo_root),
                env=env,
            )
            stdout, stderr = process.communicate(input="y\n", timeout=120)
        else:
            process = subprocess.run(
                ["bash", str(share_script)],
                capture_output=True,
                text=True,
                cwd=str(repo_root),
                timeout=120,
            )
            stdout = process.stdout
            stderr = process.stderr

        # Update last share timestamp
        last_share_file = local_patterns_dir / ".last-pattern-share"
        last_share_file.touch()

        if process.returncode == 0:
            # Extract PR URL from output if present
            pr_url = None
            for line in stdout.split("\n"):
                if "https://github.com" in line and "/pull/" in line:
                    pr_url = line.strip()
                    break

            return json.dumps(
                {
                    "status": "success",
                    "message": "Patterns shared successfully",
                    "shared": True,
                    "pr_url": pr_url,
                    "timestamp": datetime.now().isoformat(),
                    "output_summary": stdout[-500:] if len(stdout) > 500 else stdout,
                },
                indent=2,
            )
        else:
            return json.dumps(
                {
                    "status": "error",
                    "error": f"Share script failed with code {process.returncode}",
                    "shared": False,
                    "stderr": stderr[-500:] if len(stderr) > 500 else stderr,
                },
                indent=2,
            )

    except subprocess.TimeoutExpired:
        return json.dumps(
            {
                "status": "error",
                "error": "Pattern sharing timed out after 120 seconds",
                "shared": False,
            },
            indent=2,
        )
    except Exception as e:
        import traceback

        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "shared": False,
                "traceback": traceback.format_exc(),
            },
            indent=2,
        )


@mcp.resource("logs://latest")
def get_latest_logs() -> str:
    """Get the most recent build logs."""
    logs_dir = Path("logs")
    if not logs_dir.exists():
        return "No logs found"

    # Find most recent log directory
    log_dirs = sorted([d for d in logs_dir.iterdir() if d.is_dir()], reverse=True)
    if not log_dirs:
        return "No logs found"

    latest = log_dirs[0]
    session_log = latest / "session.jsonl"

    if session_log.exists():
        with open(session_log) as f:
            lines = f.readlines()
            return f"Latest log ({latest.name}):\n\n" + "\n".join(lines[-10:])

    return f"Log directory exists but no session.jsonl found: {latest}"


# ═══════════════════════════════════════════════════════════
# EVOLUTION SYSTEM TOOLS (CFES)
# ═══════════════════════════════════════════════════════════

# Import evolution tool implementations
from tools.evolution_mcp_tools import (  # noqa: E402
    create_evolution_task_impl,
    get_evolution_tasks_impl,
    start_evolution_daemon_impl,
    stop_evolution_daemon_impl,
    get_daemon_status_impl,
    register_project_impl,
    apply_pattern_to_project_impl,
    validate_project_health_impl,
    register_agent_impl,
    send_agent_message_impl,
)


@mcp.tool()
def create_evolution_task(
    task_type: str,
    target_project: Optional[str] = None,
    pattern_id: Optional[str] = None,
    priority: int = 5,
    params: Optional[Dict] = None,
) -> str:
    """Create new evolution task and add to queue. Types: self_improvement, chaos_creative, research, apply_pattern, validate."""
    return create_evolution_task_impl(
        task_type, target_project, pattern_id, priority, params
    )


@mcp.tool()
def get_evolution_tasks(status: str = "pending", limit: int = 50) -> str:
    """List evolution tasks with optional filters. Status: pending, running, completed, failed, all."""
    return get_evolution_tasks_impl(status, limit)


@mcp.tool()
def start_evolution_daemon(config_path: Optional[str] = None) -> str:
    """Start the evolution daemon service."""
    return start_evolution_daemon_impl(config_path)


@mcp.tool()
def stop_evolution_daemon(graceful: bool = True) -> str:
    """Stop the evolution daemon (gracefully waits for tasks if True)."""
    return stop_evolution_daemon_impl(graceful)


@mcp.tool()
def get_daemon_status() -> str:
    """Get daemon health, queue size, active tasks, and resource usage."""
    return get_daemon_status_impl()


@mcp.tool()
def register_project(
    project_path: str, project_type: str, metadata: Optional[Dict] = None
) -> str:
    """Register a project in the global registry."""
    return register_project_impl(project_path, project_type, metadata)


@mcp.tool()
def apply_pattern_to_project(project_path: str, pattern_id: str) -> str:
    """Apply a specific pattern to an existing project (creates task)."""
    return apply_pattern_to_project_impl(project_path, pattern_id)


@mcp.tool()
def validate_project_health(project_path: str) -> str:
    """Run tests and validate project health (creates validation task)."""
    return validate_project_health_impl(project_path)


@mcp.tool()
def register_agent(
    agent_name: str,
    agent_url: Optional[str] = None,
    capabilities: Optional[List[str]] = None,
) -> str:
    """Register an agent in the network."""
    return register_agent_impl(agent_name, agent_url, capabilities)


@mcp.tool()
def send_agent_message(target_agent: str, message_type: str, payload: Dict) -> str:
    """Send message to another agent. Types: task_delegation, learning_share, health_check."""
    return send_agent_message_impl(target_agent, message_type, payload)


def bootstrap_patterns_on_startup():
    """
    Bootstrap patterns from project directory into global storage on first run.

    This function checks if the current directory contains a Context Foundry project
    with pattern files in `.context-foundry/patterns/`. If found and not previously
    bootstrapped, it merges all project patterns into global storage.

    This ensures new users automatically benefit from community-contributed patterns
    when they clone and run Context Foundry.
    """
    try:
        import logging

        logger = logging.getLogger(__name__)

        # Check if running from a Context Foundry project directory
        project_pattern_dir = Path.cwd() / ".context-foundry" / "patterns"
        if not project_pattern_dir.exists():
            return  # Not a CF project, skip bootstrap

        # Global pattern directory
        global_pattern_dir = Path.home() / ".context-foundry" / "patterns"
        global_pattern_dir.mkdir(parents=True, exist_ok=True)

        # Check if bootstrap already done
        bootstrap_marker = global_pattern_dir / ".bootstrap-done"
        if bootstrap_marker.exists():
            return  # Already bootstrapped, skip

        logger.info(f"🔄 Bootstrapping patterns from {project_pattern_dir}")
        print(f"🔄 Bootstrapping patterns from {project_pattern_dir}", file=sys.stderr)

        # Merge all pattern files
        pattern_files_merged = 0
        total_patterns_added = 0

        for pattern_file in project_pattern_dir.glob("*.json"):
            pattern_type = pattern_file.stem  # e.g., "common-issues"

            try:
                result = _merge_project_patterns_impl(
                    str(pattern_file), pattern_type, increment_build_count=False
                )

                if result["status"] == "success":
                    pattern_files_merged += 1
                    total_patterns_added += result["merge_stats"]["new_patterns"]
                    logger.info(
                        f"✓ Merged {pattern_file.name}: {result['merge_stats']}"
                    )
                    print(
                        f"  ✓ Merged {pattern_file.name}: +{result['merge_stats']['new_patterns']} new patterns",
                        file=sys.stderr,
                    )
                else:
                    logger.warning(
                        f"✗ Failed to merge {pattern_file.name}: {result.get('error')}"
                    )
                    print(f"  ✗ Failed to merge {pattern_file.name}", file=sys.stderr)

            except Exception as e:
                logger.error(f"✗ Error merging {pattern_file}: {e}")
                print(f"  ✗ Error merging {pattern_file}: {e}", file=sys.stderr)

        # Mark as bootstrapped
        bootstrap_marker.write_text(
            f"Bootstrapped on {datetime.now().isoformat()}\n"
            f"Files merged: {pattern_files_merged}\n"
            f"New patterns added: {total_patterns_added}\n"
        )

        logger.info(
            f"✅ Bootstrap complete: {pattern_files_merged} files, {total_patterns_added} new patterns"
        )
        print(
            f"✅ Bootstrap complete: {pattern_files_merged} pattern files merged, {total_patterns_added} new patterns added\n",
            file=sys.stderr,
        )

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Bootstrap failed: {e}", exc_info=True)
        print(f"⚠️  Bootstrap warning: {e}", file=sys.stderr)
        # Don't fail startup, just log the error


if __name__ == "__main__":
    # Bootstrap patterns from project directory on first run
    bootstrap_patterns_on_startup()

    # Run the MCP server
    # This uses stdio transport which is standard for Claude Desktop
    print_banner(version="1.0.0")
    print("", file=sys.stderr)
    print("📋 Available tools:", file=sys.stderr)
    print("   - context_foundry_status: Get server status", file=sys.stderr)
    print(
        "   - delegate_to_claude_code: Delegate tasks to fresh Claude instances (synchronous)",
        file=sys.stderr,
    )
    print(
        "   - delegate_to_claude_code_async: Delegate tasks asynchronously (parallel execution)",
        file=sys.stderr,
    )
    print(
        "   - get_delegation_result: Check status and get results of async tasks",
        file=sys.stderr,
    )
    print(
        "   - list_delegations: List all active and completed async tasks",
        file=sys.stderr,
    )
    print(
        "   - cancel_delegation: Manually cancel/kill a running task", file=sys.stderr
    )
    print(
        "   - stream_delegation_output: Stream raw real-time output from running tasks",
        file=sys.stderr,
    )
    print(
        "   - autonomous_build_and_deploy: Fully autonomous Scout→Architect→Builder→Test→Deploy (runs in background)",
        file=sys.stderr,
    )
    print(
        "   - read_global_patterns: Read patterns from global pattern storage",
        file=sys.stderr,
    )
    print(
        "   - save_global_patterns: Save patterns to global pattern storage",
        file=sys.stderr,
    )
    print(
        "   - merge_project_patterns: Merge project patterns into global storage",
        file=sys.stderr,
    )
    print(
        "   - migrate_all_project_patterns: Migrate all project patterns to global storage",
        file=sys.stderr,
    )
    print(
        "   - share_patterns_to_community: Automatically share patterns to community (creates PR)",
        file=sys.stderr,
    )
    print("", file=sys.stderr)
    print("🔄 Evolution System Tools (CFES):", file=sys.stderr)
    print("   - create_evolution_task: Create new evolution task", file=sys.stderr)
    print("   - get_evolution_tasks: List tasks with filters", file=sys.stderr)
    print("   - start_evolution_daemon: Start evolution daemon", file=sys.stderr)
    print("   - stop_evolution_daemon: Stop evolution daemon", file=sys.stderr)
    print("   - get_daemon_status: Get daemon status and metrics", file=sys.stderr)
    print("   - register_project: Register project in registry", file=sys.stderr)
    print("   - apply_pattern_to_project: Apply pattern to project", file=sys.stderr)
    print("   - validate_project_health: Validate project health", file=sys.stderr)
    print("   - register_agent: Register agent in network", file=sys.stderr)
    print("   - send_agent_message: Send inter-agent message", file=sys.stderr)
    print(
        "💡 Configure in Claude Desktop or Claude Code CLI to use this server!",
        file=sys.stderr,
    )

    mcp.run()
