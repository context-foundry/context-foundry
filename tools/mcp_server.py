#!/usr/bin/env python3
"""
MCP Server for Context Foundry
Enables Claude Desktop to use Context Foundry without API charges
"""

import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add parent directory to path for imports (must be before local imports!)
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import version management (single source of truth)
from tools.version import get_version

# Import BAML integration for type-safe phase tracking

# Import safety mechanisms for sandbox enforcement

# Import Context Codex for knowledge management
from context_foundry.codex import KnowledgeStore

# Import S3 client for community pattern sync
from context_foundry.storage import S3PatternClient

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
from tools.mcp_utils.output_utils import truncate_output, create_output_summary
from tools.mcp_utils.phase_tracking import read_phase_info
from tools.mcp_utils.path_utils import get_context_foundry_parent_dir
from tools.mcp_utils.project_detection import detect_existing_codebase
from tools.mcp_utils.task_classification import detect_task_intent
from tools.mcp_utils.pattern_management import (
    read_global_patterns_impl,
    save_global_patterns_impl,
    merge_project_patterns_impl,
    migrate_all_project_patterns_impl,
    share_patterns_to_community_impl,
    bootstrap_patterns_on_startup_impl,
)
from tools.mcp_utils.delegation import (
    _write_delegation_metadata,  # noqa: F401
    _write_full_output_to_file,  # noqa: F401
    delegate_to_claude_code_impl,
    delegate_to_claude_code_async_impl,
    get_delegation_result_impl,
    list_delegations_impl,
    cancel_delegation_impl,
    stream_delegation_output_impl,
)
from tools.mcp_utils.autonomous_build import autonomous_build_and_deploy_impl
from tools.mcp_utils.filesystem_tools import (
    discover_all_tools,
    search_tools_by_query,
    get_scanner,
)

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
_migrate_all_project_patterns_impl = migrate_all_project_patterns_impl
_share_patterns_to_community_impl = share_patterns_to_community_impl
_bootstrap_patterns_on_startup_impl = bootstrap_patterns_on_startup_impl
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

# Initialize Context Codex (global knowledge store)
# Database location: ~/.context-foundry/codex.db
_codex_db_path = Path.home() / ".context-foundry" / "codex.db"
_codex_store = None


def _get_codex_store() -> KnowledgeStore:
    """Get or create the global KnowledgeStore instance."""
    global _codex_store
    if _codex_store is None:
        _codex_store = KnowledgeStore(_codex_db_path)
    return _codex_store


# Track async delegation tasks
# Structure: {task_id: {process, cmd, cwd, start_time, status, result, stdout, stderr, duration}}
active_tasks: Dict[str, Dict[str, Any]] = {}


# ANCHOR: read_phase_info
# Moved to tools/mcp_utils/phase_tracking.py - imported above with re-export as _read_phase_info

# ANCHOR: get_context_foundry_parent_dir
# Moved to tools/mcp_utils/path_utils.py - imported above with re-export as _get_context_foundry_parent_dir

# ANCHOR: truncate_output
# Moved to tools/mcp_utils/output_utils.py - imported above with re-export as _truncate_output

# ANCHOR: write_delegation_metadata
# Moved to tools/mcp_utils/delegation.py - imported above

# ANCHOR: write_full_output_to_file
# Moved to tools/mcp_utils/delegation.py - imported above


# ANCHOR: create_output_summary
# Moved to tools/mcp_utils/output_utils.py - imported above with re-export as _create_output_summary


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


# ANCHOR: search_tools
@mcp.tool()
def search_tools(
    query: str,
    category: Optional[str] = None,
    detail_level: str = "standard",
) -> str:
    """
    Search for filesystem-based tools using progressive discovery.

    This implements the progressive tool discovery pattern from Anthropic's
    code execution guide. Instead of loading all tool definitions into context,
    agents can search for tools on-demand, dramatically reducing token usage.

    Args:
        query: Search query (matches tool name and description)
        category: Optional category filter (e.g., "delegation", "codex", "patterns")
        detail_level: Level of detail in results
            - "minimal": Just names and brief descriptions
            - "standard": Includes function signatures (default)
            - "full": Complete details with examples

    Returns:
        JSON string with search results

    Examples:
        # Find delegation tools
        search_tools("delegate", category="delegation")

        # Search for codex tools with full details
        search_tools("codex", detail_level="full")

        # Find all pattern management tools
        search_tools("pattern", category="patterns")
    """
    try:
        results = search_tools_by_query(query, category, detail_level)

        if not results:
            return json.dumps(
                {
                    "found": 0,
                    "message": f"No tools found matching '{query}'",
                    "suggestions": [
                        "Try broader search terms",
                        "Check available categories with context_foundry_status",
                        "Browse ~/.context-foundry/tools/ directory",
                    ],
                }
            )

        scanner = get_scanner()
        categories = scanner.get_categories()

        return json.dumps(
            {
                "found": len(results),
                "query": query,
                "category_filter": category,
                "detail_level": detail_level,
                "results": results,
                "available_categories": list(categories),
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"error": f"Search failed: {str(e)}"})


# ANCHOR: delegate_to_claude_code
# Moved to tools/mcp_utils/delegation.py
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
# Moved to tools/mcp_utils/delegation.py
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
# Moved to tools/mcp_utils/delegation.py
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
# Moved to tools/mcp_utils/delegation.py
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
# Moved to tools/mcp_utils/delegation.py
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
# Moved to tools/mcp_utils/delegation.py
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
# Moved to tools/mcp_utils/project_detection.py - imported above with re-export as _detect_existing_codebase

# ANCHOR: detect_task_intent
# Moved to tools/mcp_utils/task_classification.py - imported above with re-export as _detect_task_intent


def _autonomous_build_and_deploy_impl(
    task: str,
    working_directory: str,
    github_repo_name: Optional[str] = None,
    existing_repo: Optional[str] = None,
    mode: str = "new_project",
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
    # Moved to tools/mcp_utils/autonomous_build.py - imported above with re-export as _autonomous_build_and_deploy_impl
    # NOTE: enable_test_loop removed - testing is now automatic
    return autonomous_build_and_deploy_impl(
        task=task,
        working_directory=working_directory,
        github_repo_name=github_repo_name,
        existing_repo=existing_repo,
        mode=mode,
        max_test_iterations=max_test_iterations,
        timeout_minutes=timeout_minutes,
        use_parallel=use_parallel,
        incremental=incremental,
        force_rebuild=force_rebuild,
        sandbox_path=sandbox_path,
        sandbox_task_id=sandbox_task_id,
        active_tasks=active_tasks,
    )


# MCP tool wrapper (submits to CF Daemon)
@mcp.tool()
def autonomous_build_and_deploy(
    task: str,
    working_directory: str,
    github_repo_name: Optional[str] = None,
    existing_repo: Optional[str] = None,
    mode: str = "new_project",
    max_test_iterations: int = 3,
    timeout_minutes: float = 90.0,
    use_parallel: bool = False,
    incremental: bool = False,
    force_rebuild: bool = False,
) -> str:
    """
    Submit autonomous build job to CF Daemon queue.

    This tool now delegates to the Context Foundry Daemon instead of spawning
    processes directly. The daemon provides:
    - Job persistence (survives disconnections)
    - Working directory locking (prevents conflicts)
    - Progress monitoring via CLI (cfd logs <job-id> --follow)
    - Automatic retry on failures
    - Pattern merging and self-improvement

    Testing is automatic - runs whenever code is detected in the project.

    Prerequisites:
    - CF Daemon must be running: `cfd start`
    - Check daemon status: `cfd status`

    Returns:
        JSON with job_id and monitoring instructions
    """
    from tools.mcp_utils.daemon_integration import submit_autonomous_build_to_daemon

    return submit_autonomous_build_to_daemon(
        task=task,
        working_directory=working_directory,
        github_repo_name=github_repo_name,
        mode=mode,
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
    # Moved to tools/mcp_utils/pattern_management.py - imported above with re-export as _read_global_patterns_impl
    return read_global_patterns_impl(pattern_type)


def _save_global_patterns_impl(pattern_type: str, data: dict) -> dict:
    # ANCHOR: save_global_patterns
    # Moved to tools/mcp_utils/pattern_management.py - imported above with re-export as _save_global_patterns_impl
    return save_global_patterns_impl(pattern_type, data)


def _merge_project_patterns_impl(
    project_pattern_file: str,
    pattern_type: str = "common-issues",
    increment_build_count: bool = True,
) -> dict:
    # ANCHOR: merge_project_patterns
    # Moved to tools/mcp_utils/pattern_management.py - imported above with re-export as _merge_project_patterns_impl
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
    # ANCHOR: migrate_all_project_patterns
    # Moved to tools/mcp_utils/pattern_management.py - imported above with re-export as _migrate_all_project_patterns_impl
    return migrate_all_project_patterns_impl(
        projects_base_dir=projects_base_dir,
        projects_dir=projects_dir,
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
    # ANCHOR: share_patterns_to_community
    # Moved to tools/mcp_utils/pattern_management.py - imported above with re-export as _share_patterns_to_community_impl
    return share_patterns_to_community_impl(
        auto_confirm=auto_confirm,
        skip_if_no_changes=skip_if_no_changes,
        project_path=project_path,
        pattern_ids=pattern_ids,
        description=description,
    )


# ========== S3 Pattern Sync Tools (AWS Integration) ==========


@mcp.tool()
def sync_patterns_to_s3(
    pattern_type: str = "common-issues",
    force: bool = False,
) -> str:
    """
    Upload local patterns to S3 community repository.

    Syncs patterns from ~/.context-foundry/patterns/ to
    s3://bedrock-builder-kb-898587418237/community-patterns/

    Args:
        pattern_type: Type of pattern to upload ("common-issues", "scout-learnings",
                     "architecture-patterns", "test-patterns", "mcp-server-patterns")
        force: Force upload even if S3 version is newer

    Returns:
        JSON string with upload status and metadata

    Examples:
        # Upload common issues to S3
        result = sync_patterns_to_s3("common-issues")

        # Force upload even if conflicts exist
        result = sync_patterns_to_s3("scout-learnings", force=True)
    """
    try:
        client = S3PatternClient()
        result = client.upload_pattern(pattern_type, force=force)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps(
            {"success": False, "error": f"S3 sync failed: {str(e)}"}, indent=2
        )


@mcp.tool()
def pull_patterns_from_s3(
    pattern_type: str = "common-issues",
    force: bool = False,
) -> str:
    """
    Download community patterns from S3 to local cache.

    Downloads patterns from s3://bedrock-builder-kb-898587418237/community-patterns/
    to ~/.context-foundry/patterns/

    Args:
        pattern_type: Type of pattern to download ("common-issues", "scout-learnings",
                     "architecture-patterns", "test-patterns", "mcp-server-patterns")
        force: Force download even if local version is newer

    Returns:
        JSON string with download status and metadata

    Examples:
        # Download latest common issues from S3
        result = pull_patterns_from_s3("common-issues")

        # Force download to overwrite local changes
        result = pull_patterns_from_s3("architecture-patterns", force=True)
    """
    try:
        client = S3PatternClient()
        result = client.download_pattern(pattern_type, force=force)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps(
            {"success": False, "error": f"S3 download failed: {str(e)}"}, indent=2
        )


@mcp.tool()
def list_s3_community_patterns(
    pattern_type: Optional[str] = None,
) -> str:
    """
    List available community patterns in S3.

    Browses s3://bedrock-builder-kb-898587418237/community-patterns/ to see
    what patterns are available for download.

    Args:
        pattern_type: Filter by specific pattern type (optional)

    Returns:
        JSON string with list of available patterns and metadata

    Examples:
        # List all community patterns
        patterns = list_s3_community_patterns()

        # List only common-issues patterns
        patterns = list_s3_community_patterns("common-issues")
    """
    try:
        client = S3PatternClient()
        result = client.list_community_patterns(pattern_type=pattern_type)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps(
            {"success": False, "error": f"S3 list failed: {str(e)}"}, indent=2
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


# ========== Context Codex Tools ==========


@mcp.tool()
def codex_search(
    query: str,
    entry_type: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 10,
) -> str:
    """
    Search the Context Codex knowledge base using full-text search.

    Args:
        query: Search query (searches title, description, and tags)
        entry_type: Optional filter by type (issue, pattern, learning, etc.)
        category: Optional filter by category
        limit: Maximum results to return (default: 10)

    Returns:
        JSON string with search results including entry ID, title, type, and description

    Examples:
        - codex_search("docker volume") - Find all knowledge about docker volumes
        - codex_search("authentication", entry_type="issue") - Find auth issues
        - codex_search("test patterns", category="test-pattern") - Find test patterns
    """
    store = _get_codex_store()

    # Build filters
    filters = {}
    if entry_type:
        filters["type"] = entry_type
    if category:
        filters["category"] = category

    # Search
    results = store.search(query, filters=filters if filters else None)[:limit]

    if not results:
        return json.dumps(
            {"found": 0, "query": query, "message": "No results found"}, indent=2
        )

    # Format results
    formatted_results = []
    for entry in results:
        formatted_results.append(
            {
                "id": entry.id,
                "type": entry.type.value,
                "category": entry.category,
                "title": entry.title,
                "description": entry.description or "",
                "severity": entry.severity.value if entry.severity else None,
                "frequency": entry.frequency,
                "tags": entry.tags,
            }
        )

    return json.dumps(
        {"found": len(results), "query": query, "results": formatted_results}, indent=2
    )


@mcp.tool()
def codex_get_entry(entry_id: str) -> str:
    """
    Get detailed information about a specific knowledge entry.

    Args:
        entry_id: Entry ID (e.g., "iss-123", "pat-456")

    Returns:
        JSON string with complete entry details including solutions and evidence

    Example:
        codex_get_entry("iss-docker-volume-001")
    """
    store = _get_codex_store()

    entry = store.get_entry(entry_id)
    if not entry:
        return json.dumps({"error": f"Entry '{entry_id}' not found"}, indent=2)

    # Get related data
    solutions = store.get_solutions(entry_id)
    evidence = store.get_evidence(entry_id)
    projects = store.get_projects_for_entry(entry_id)

    result = {
        "entry": {
            "id": entry.id,
            "type": entry.type.value,
            "category": entry.category,
            "title": entry.title,
            "description": entry.description,
            "severity": entry.severity.value if entry.severity else None,
            "confidence": entry.confidence,
            "frequency": entry.frequency,
            "tags": entry.tags,
            "project_types": entry.project_types,
            "status": entry.status.value,
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat(),
            "last_seen_at": entry.last_seen_at.isoformat()
            if entry.last_seen_at
            else None,
        },
        "solutions": [
            {
                "id": sol.id,
                "phase": sol.phase,
                "description": sol.description,
                "auto_apply": sol.auto_apply,
                "success_rate": sol.success_rate,
            }
            for sol in solutions
        ],
        "evidence": [
            {
                "id": ev.id,
                "type": ev.evidence_type,
                "description": ev.description,
                "code_snippet": ev.code_snippet,
            }
            for ev in evidence
        ],
        "projects": [
            {
                "project_path": proj.project_path,
                "project_type": proj.project_type,
                "occurrence_count": proj.occurrence_count,
                "first_seen": proj.first_seen.isoformat(),
                "last_seen": proj.last_seen.isoformat(),
            }
            for proj in projects
        ],
        "total_projects": len(projects),
    }

    return json.dumps(result, indent=2)


@mcp.tool()
def codex_add_issue(
    title: str,
    description: str,
    severity: str = "MEDIUM",
    tags: Optional[List[str]] = None,
    project_types: Optional[List[str]] = None,
    solution_description: Optional[str] = None,
) -> str:
    """
    Add a new issue to the Context Codex.

    Args:
        title: Short title for the issue
        description: Detailed description of the issue
        severity: Severity level (LOW, MEDIUM, HIGH, CRITICAL)
        tags: Optional list of tags (e.g., ["docker", "volumes"])
        project_types: Optional list of project types (e.g., ["python", "nodejs"])
        solution_description: Optional solution/workaround description

    Returns:
        JSON string with the created entry ID

    Example:
        codex_add_issue(
            "Docker volume persists old config",
            "After changing config, volumes keep old data",
            severity="MEDIUM",
            tags=["docker", "volumes"],
            solution_description="Remove volume before rebuild: docker-compose down -v"
        )
    """
    from context_foundry.codex import (
        KnowledgeEntry,
        KnowledgeType,
        Severity,
        Solution,
        generate_entry_id,
    )
    import uuid

    store = _get_codex_store()

    # Create entry
    entry = KnowledgeEntry(
        id=generate_entry_id("issue", title),
        type=KnowledgeType.ISSUE,
        category="common-issue",
        title=title,
        description=description,
        severity=Severity(severity.upper()),
        tags=tags or [],
        project_types=project_types or [],
    )

    entry_id = store.add_entry(entry)

    # Add solution if provided
    if solution_description:
        solution = Solution(
            id=str(uuid.uuid4()),
            entry_id=entry_id,
            description=solution_description,
            auto_apply=False,
        )
        store.add_solution(solution)

    return json.dumps(
        {
            "success": True,
            "entry_id": entry_id,
            "message": f"Issue '{title}' added to Context Codex",
        },
        indent=2,
    )


@mcp.tool()
def codex_add_pattern(
    title: str,
    description: str,
    category: str,
    tags: Optional[List[str]] = None,
    project_types: Optional[List[str]] = None,
) -> str:
    """
    Add a new pattern/best practice to the Context Codex.

    Args:
        title: Short title for the pattern
        description: Detailed description of the pattern
        category: Pattern category (e.g., "architecture", "test-pattern")
        tags: Optional list of tags
        project_types: Optional list of applicable project types

    Returns:
        JSON string with the created entry ID

    Example:
        codex_add_pattern(
            "Use named volumes for persistence",
            "Named volumes provide better data persistence than bind mounts",
            category="architecture",
            tags=["docker", "best-practice"]
        )
    """
    from context_foundry.codex import (
        KnowledgeEntry,
        KnowledgeType,
        generate_entry_id,
    )

    store = _get_codex_store()

    entry = KnowledgeEntry(
        id=generate_entry_id("pattern", title),
        type=KnowledgeType.PATTERN,
        category=category,
        title=title,
        description=description,
        tags=tags or [],
        project_types=project_types or [],
    )

    entry_id = store.add_entry(entry)

    return json.dumps(
        {
            "success": True,
            "entry_id": entry_id,
            "message": f"Pattern '{title}' added to Context Codex",
        },
        indent=2,
    )


# ============================================================================
# Reusable Skills Management
# ============================================================================


@mcp.tool()
def save_skill(
    title: str,
    description: str,
    implementation_code: str,
    file_type: str,
    project_type: str,
    tags: Optional[List[str]] = None,
    requirements: Optional[List[str]] = None,
    file_path: Optional[str] = None,
    example: Optional[str] = None,
) -> str:
    """
    Save a reusable skill to ~/.context-foundry/skills/

    Captures successful implementations as reusable skills for future builds.
    Skills are stored as JSON files with auto-generated markdown documentation
    and indexed in Context Codex for fast search.

    Args:
        title: Skill name (e.g., "JWT Authentication Implementation")
        description: Detailed description of what this skill does
        implementation_code: Complete, working code implementation
        file_type: Programming language (python, typescript, javascript, go, etc.)
        project_type: Project framework/context (fastapi, react, express, etc.)
        tags: Keywords for search (e.g., ["authentication", "jwt", "security"])
        requirements: Dependencies needed (e.g., ["PyJWT>=2.8.0", "python-jose"])
        file_path: Suggested file path for this code (e.g., "auth/jwt_handler.py")
        example: Usage example code

    Returns:
        JSON string with skill_id and storage locations

    Examples:
        save_skill(
            title="JWT Authentication for FastAPI",
            description="Complete JWT token generation, validation, and refresh",
            implementation_code=jwt_handler_code,
            file_type="python",
            project_type="fastapi",
            tags=["authentication", "jwt", "security"],
            requirements=["PyJWT>=2.8.0", "python-jose[cryptography]"],
            file_path="auth/jwt_handler.py",
            example="from auth.jwt_handler import verify_token\\n..."
        )
    """
    from tools.skills.manager import SkillsManager

    try:
        manager = SkillsManager()

        skill_id = manager.save_skill(
            title=title,
            description=description,
            code=implementation_code,
            file_type=file_type,
            project_type=project_type,
            tags=tags or [],
            requirements=requirements or [],
            file_path=file_path,
            example=example,
        )

        # Get skill details for response
        skill = manager.load_skill(skill_id)
        category = skill["metadata"]["category"] if skill else "unknown"

        return json.dumps(
            {
                "success": True,
                "skill_id": skill_id,
                "category": category,
                "json_file": f"~/.context-foundry/skills/{category}/{skill_id}.json",
                "markdown_file": f"~/.context-foundry/skills/{category}/{skill_id}.md",
                "message": f"Skill '{title}' saved successfully",
            },
            indent=2,
        )

    except Exception as e:
        import traceback

        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            },
            indent=2,
        )


@mcp.tool()
def search_skills(
    query: str,
    project_type: Optional[str] = None,
    min_success_rate: float = 0.0,
    limit: int = 10,
) -> str:
    """
    Search for existing reusable skills before implementing from scratch.

    Searches the skills library using query matching (title, description, tags)
    and filters by project type and success rate. Use this in Scout phase to
    find existing implementations that can be reused.

    Args:
        query: Search query (e.g., "JWT authentication", "database connection pool")
        project_type: Filter by project type (e.g., "fastapi", "react", "express")
        min_success_rate: Minimum success rate (0.0-1.0, default 0.0). Use 0.7 for high-confidence skills.
        limit: Maximum number of results (default 10)

    Returns:
        JSON string with list of matching skills

    Examples:
        # Find JWT auth implementations for FastAPI projects
        search_skills("JWT authentication", project_type="fastapi", min_success_rate=0.7)

        # Find any database connection pooling skills
        search_skills("database connection pool", min_success_rate=0.6)

        # Find React component patterns
        search_skills("react component", project_type="react")
    """
    from tools.skills.manager import SkillsManager

    try:
        manager = SkillsManager()

        results = manager.search_skills(
            query=query,
            project_type=project_type,
            min_success_rate=min_success_rate,
            limit=limit,
        )

        # Format results for display
        formatted_results = []
        for skill in results:
            success_rate_pct = (
                f"{skill['success_rate'] * 100:.0f}%"
                if skill.get("success_rate") is not None
                else "Not yet used"
            )

            formatted_results.append(
                {
                    "skill_id": skill["skill_id"],
                    "title": skill["title"],
                    "category": skill["category"],
                    "project_type": skill["project_type"],
                    "success_rate": success_rate_pct,
                    "usage_count": skill["usage_count"],
                    "tags": skill["tags"],
                }
            )

        return json.dumps(
            {
                "success": True,
                "query": query,
                "filters": {
                    "project_type": project_type,
                    "min_success_rate": min_success_rate,
                },
                "total_results": len(formatted_results),
                "results": formatted_results,
                "message": f"Found {len(formatted_results)} matching skill(s)",
            },
            indent=2,
        )

    except Exception as e:
        import traceback

        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            },
            indent=2,
        )


@mcp.tool()
def load_skill(skill_id: str) -> str:
    """
    Load complete skill details including implementation code.

    Retrieves the full skill definition with code, dependencies, usage examples,
    and metrics. Use this after search_skills() to get the complete implementation
    for a skill you want to reuse.

    Args:
        skill_id: Skill ID (e.g., "skl-jwt-auth-001")

    Returns:
        JSON string with complete skill details

    Example:
        # After searching, load full details
        load_skill("skl-jwt-auth-001")
    """
    from tools.skills.manager import SkillsManager

    try:
        manager = SkillsManager()

        skill = manager.load_skill(skill_id)

        if not skill:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Skill not found: {skill_id}",
                },
                indent=2,
            )

        # Format success rate
        success_rate = skill["metrics"].get("success_rate")
        if success_rate is not None:
            success_rate_display = f"{success_rate * 100:.0f}%"
        else:
            success_rate_display = "Not yet used"

        return json.dumps(
            {
                "success": True,
                "skill_id": skill_id,
                "title": skill["metadata"]["title"],
                "description": skill["metadata"]["description"],
                "category": skill["metadata"]["category"],
                "file_type": skill["metadata"]["file_type"],
                "project_type": skill["metadata"]["project_type"],
                "implementation": {
                    "code": skill["implementation"]["code"],
                    "file_path": skill["implementation"]["file_path"],
                    "dependencies": skill["implementation"]["dependencies"],
                },
                "usage": skill["usage"],
                "metrics": {
                    "usage_count": skill["metrics"]["usage_count"],
                    "success_rate": success_rate_display,
                    "last_used": skill["metrics"]["last_used"],
                    "projects_used": skill["metrics"]["projects_used"],
                },
                "tags": skill["tags"],
                "created_at": skill["created_at"],
                "updated_at": skill["updated_at"],
            },
            indent=2,
        )

    except Exception as e:
        import traceback

        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            },
            indent=2,
        )


@mcp.tool()
def update_skill_metrics(skill_id: str, project_name: str, success: bool) -> str:
    """
    Update skill effectiveness metrics after using it in a build.

    Tracks which projects used this skill and whether it was successful.
    Updates success_rate based on historical usage. Call this in Feedback
    phase after build completes.

    Args:
        skill_id: Skill ID that was used (e.g., "skl-jwt-auth-001")
        project_name: Name/path of project that used this skill
        success: Whether the build/tests passed successfully (True/False)

    Returns:
        JSON string with updated metrics

    Example:
        # After build completes successfully
        update_skill_metrics(
            skill_id="skl-jwt-auth-001",
            project_name="ecommerce-api",
            success=True
        )

        # After build failed
        update_skill_metrics(
            skill_id="skl-db-pool-002",
            project_name="analytics-service",
            success=False
        )
    """
    from tools.skills.manager import SkillsManager

    try:
        manager = SkillsManager()

        # Update metrics
        updated = manager.update_metrics(
            skill_id=skill_id, project_name=project_name, success=success
        )

        if not updated:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to update metrics for {skill_id}",
                },
                indent=2,
            )

        # Get updated skill
        skill = manager.load_skill(skill_id)

        if not skill:
            return json.dumps(
                {"success": False, "error": "Skill not found after update"},
                indent=2,
            )

        # Format metrics
        metrics = skill["metrics"]
        success_rate_pct = (
            f"{metrics['success_rate'] * 100:.0f}%"
            if metrics.get("success_rate") is not None
            else "0%"
        )

        return json.dumps(
            {
                "success": True,
                "skill_id": skill_id,
                "title": skill["metadata"]["title"],
                "updated_metrics": {
                    "usage_count": metrics["usage_count"],
                    "success_rate": success_rate_pct,
                    "last_used": metrics["last_used"],
                    "total_projects": len(metrics["projects_used"]),
                },
                "this_usage": {
                    "project_name": project_name,
                    "success": success,
                },
                "message": f"Updated metrics for '{skill['metadata']['title']}'",
            },
            indent=2,
        )

    except Exception as e:
        import traceback

        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            },
            indent=2,
        )


# ============================================================================
# CODE SANDBOX - In-Execution Data Filtering
# ============================================================================
# Implements Anthropic's in-execution data filtering pattern
# https://www.anthropic.com/engineering/code-execution-with-mcp


@mcp.tool()
def execute_sandbox_code(
    code: str,
    context: dict = None,
    timeout: int = 30,
    max_memory_mb: int = 512,
) -> str:
    """
    Execute Python code in secure sandbox for data filtering.

    This implements Anthropic's in-execution data filtering pattern,
    enabling agents to process large datasets and return only filtered
    results. Achieves 98%+ token savings on data-heavy workflows.

    **Use Case**: Process 10,000 spreadsheet rows, return only 5 matching rows
    instead of loading all 10,000 into context.

    **Security**: Isolated subprocess, timeout enforcement, forbidden imports blocked.

    Args:
        code: Python code to execute. Should set 'result' variable with output.
        context: Dictionary of variables to make available in code (optional)
        timeout: Maximum execution time in seconds (default: 30)
        max_memory_mb: Maximum memory in megabytes (default: 512)

    Returns:
        JSON string with:
            - success: bool (True if executed without errors)
            - result: Any (the value of 'result' variable in code)
            - stdout: str (captured print output)
            - stderr: str (captured errors if any)

    Examples:
        # Filter large dataset
        execute_sandbox_code(
            code='''
            filtered = [row for row in data if row['status'] == 'pending']
            result = filtered[:5]  # Only return 5 rows
            ''',
            context={'data': fetch_10000_rows()}
        )

        # Aggregate data
        execute_sandbox_code(
            code='''
            total = sum(row['amount'] for row in transactions)
            result = {'total': total, 'count': len(transactions)}
            ''',
            context={'transactions': fetch_transactions()}
        )

        # Process and transform
        execute_sandbox_code(
            code='''
            import json
            import statistics
            values = [float(row['price']) for row in items]
            result = {
                'mean': statistics.mean(values),
                'median': statistics.median(values),
                'count': len(values)
            }
            ''',
            context={'items': fetch_items()}
        )

    Allowed imports:
        json, math, datetime, re, itertools, functools, collections,
        statistics, random

    Forbidden operations:
        import os, import subprocess, eval, exec, open, file I/O,
        network access, __import__

    **Token Savings Example** (from Anthropic article):
        - Without sandbox: Load 10,000 rows into context (150,000 tokens)
        - With sandbox: Return 5 filtered rows (2,000 tokens)
        - Savings: 98.7% reduction
    """
    from tools.sandbox import execute_sandbox_code as sandbox_exec

    try:
        # Execute in sandbox
        output = sandbox_exec(
            code=code,
            context=context,
            timeout=timeout,
            max_memory_mb=max_memory_mb,
        )

        return json.dumps(output, indent=2)

    except Exception as e:
        import traceback

        return json.dumps(
            {
                "success": False,
                "result": None,
                "stdout": "",
                "stderr": f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}",
            },
            indent=2,
        )


@mcp.tool()
def codex_stats() -> str:
    """
    Get Context Codex statistics.

    Returns:
        JSON string with statistics about the knowledge base including
        total entries, entries by type, and top issues

    Example:
        codex_stats()
    """
    store = _get_codex_store()
    stats = store.get_stats()

    return json.dumps(stats, indent=2)


@mcp.tool()
def export_codex_to_patterns(
    pattern_type: str = "all",
    sync_to_s3: bool = True,
) -> str:
    """
    Export Context Codex entries to legacy JSON pattern files and optionally sync to S3.

    This bridges the gap between the modern codex.db database and the legacy JSON
    pattern files that are synced to S3 and read by agents during builds.

    After export, the patterns become available to:
    - Scout/Architect/Builder agents (they read JSON files during builds)
    - Community via S3 sync
    - Pattern merging workflows

    Args:
        pattern_type: Type to export ("all", "issues", "patterns")
        sync_to_s3: Whether to auto-sync exported files to S3 (default: True)

    Returns:
        JSON string with export and sync results

    Examples:
        # Export all codex entries and sync to S3
        export_codex_to_patterns()

        # Export only issues
        export_codex_to_patterns("issues")

        # Export without S3 sync
        export_codex_to_patterns("all", sync_to_s3=False)
    """
    from tools.mcp_utils.codex_export import export_codex_to_patterns_impl

    try:
        # Export codex to JSON files
        export_result = export_codex_to_patterns_impl(pattern_type)

        if not export_result.get("success"):
            return json.dumps(export_result, indent=2)

        # Sync to S3 if requested
        s3_results = []
        if sync_to_s3:
            try:
                from context_foundry.storage import S3PatternClient

                client = S3PatternClient()
                if client.enabled:
                    # Determine which files to sync based on what was exported
                    files_to_sync = []
                    if pattern_type in ("all", "issues"):
                        files_to_sync.append("common-issues")
                    if pattern_type in ("all", "patterns"):
                        files_to_sync.append("architecture-patterns")

                    for file_type in files_to_sync:
                        s3_result = client.upload_pattern(file_type, force=True)
                        s3_results.append(
                            {
                                "pattern_type": file_type,
                                "success": s3_result.get("success"),
                                "version_id": s3_result.get("version_id"),
                                "s3_uri": s3_result.get("s3_uri"),
                            }
                        )
                else:
                    s3_results.append(
                        {
                            "warning": "S3 client not enabled (boto3 not installed)",
                            "files_exported": "Files exported locally but not synced to S3",
                        }
                    )
            except Exception as e:
                s3_results.append({"s3_sync_error": str(e)})

        # Build final result
        result = {
            "success": True,
            "export": export_result,
            "s3_sync": s3_results if sync_to_s3 else "Skipped (sync_to_s3=False)",
            "message": f"{export_result.get('message', 'Export completed')}. "
            + (
                f"Synced {len(s3_results)} file(s) to S3."
                if sync_to_s3 and s3_results
                else ""
            ),
        }

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        import traceback

        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            },
            indent=2,
        )


def bootstrap_patterns_on_startup():
    """
    Bootstrap patterns from project directory into global storage on first run.

    This function checks if the current directory contains a Context Foundry project
    with pattern files in `.context-foundry/patterns/`. If found and not previously
    bootstrapped, it merges all project patterns into global storage.

    This ensures new users automatically benefit from community-contributed patterns
    when they clone and run Context Foundry.
    """
    # ANCHOR: bootstrap_patterns_on_startup
    # Moved to tools/mcp_utils/pattern_management.py - imported above with re-export as _bootstrap_patterns_on_startup_impl
    return bootstrap_patterns_on_startup_impl()


def bootstrap_filesystem_tools():
    """
    Bootstrap filesystem-based tool discovery on startup.

    Discovers all tools in ~/.context-foundry/tools/ directory and makes them
    available for progressive discovery. This implements the filesystem-based
    tool discovery pattern from:
    https://www.anthropic.com/engineering/code-execution-with-mcp

    Tools are loaded on-demand rather than all at once, reducing context usage.
    """
    import sys

    try:
        tools = discover_all_tools(force_refresh=False)
        if tools:
            categories = get_scanner().get_categories()
            print(
                f"🔧 Discovered {len(tools)} filesystem tools in {len(categories)} categories",
                file=sys.stderr,
            )
            for category in categories:
                category_tools = [t for t in tools if t.category == category]
                print(f"   - {category}: {len(category_tools)} tools", file=sys.stderr)
        else:
            print(
                "ℹ️  No filesystem tools found in ~/.context-foundry/tools/",
                file=sys.stderr,
            )
            print(
                "   Create tools following: docs/FILESYSTEM_TOOLS.md", file=sys.stderr
            )
    except Exception as e:
        print(f"⚠️  Failed to bootstrap filesystem tools: {e}", file=sys.stderr)


if __name__ == "__main__":
    # Bootstrap patterns from project directory on first run
    bootstrap_patterns_on_startup()

    # Bootstrap filesystem-based tool discovery
    bootstrap_filesystem_tools()

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
    print("📚 Context Codex Tools (Knowledge Management):", file=sys.stderr)
    print(
        "   - codex_search: Search knowledge base with full-text search",
        file=sys.stderr,
    )
    print(
        "   - codex_get_entry: Get detailed info about a knowledge entry",
        file=sys.stderr,
    )
    print(
        "   - codex_add_issue: Add new issue/problem to knowledge base", file=sys.stderr
    )
    print("   - codex_add_pattern: Add new pattern/best practice", file=sys.stderr)
    print("   - codex_stats: Get knowledge base statistics", file=sys.stderr)
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
