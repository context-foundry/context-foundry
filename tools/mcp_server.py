#!/usr/bin/env python3
"""
MCP Server for Context Foundry
Enables Claude Desktop to use Context Foundry without API charges
"""

import os
import sys
import json
import asyncio
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# Check if FastMCP is available
try:
    from fastmcp import FastMCP, Context
    from fastmcp.server.dependencies import get_context
except ImportError:
    print("❌ Error: FastMCP not installed", file=sys.stderr)
    print("", file=sys.stderr)
    print("MCP Server mode requires Python 3.10+ and the fastmcp package.", file=sys.stderr)
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

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.banner import print_banner

# Create MCP server
mcp = FastMCP("Context Foundry")

# Track active builds
active_builds = {}

# Track async delegation tasks
# Structure: {task_id: {process, cmd, cwd, start_time, status, result, stdout, stderr, duration}}
active_tasks: Dict[str, Dict[str, Any]] = {}


def _read_phase_info(working_directory: str) -> Dict[str, Any]:
    """
    Read phase tracking information from .context-foundry/current-phase.json

    Returns dict with phase info, or empty dict if file doesn't exist or is invalid.
    """
    try:
        phase_file = Path(working_directory) / ".context-foundry" / "current-phase.json"
        if not phase_file.exists():
            return {}

        with open(phase_file, 'r') as f:
            phase_data = json.load(f)

        return phase_data
    except (json.JSONDecodeError, FileNotFoundError, PermissionError):
        # File doesn't exist yet, is invalid JSON, or can't be read
        return {}
    except Exception:
        # Any other error - return empty dict
        return {}


def _get_context_foundry_parent_dir() -> Path:
    """
    Get the parent directory of Context Foundry installation.

    This allows projects to be created as siblings of Context Foundry itself.

    Example:
        If Context Foundry is at: /Users/name/homelab/context-foundry
        This returns: /Users/name/homelab

        So new projects get created at: /Users/name/homelab/project-name

    Returns:
        Path to Context Foundry's parent directory
    """
    # __file__ is tools/mcp_server.py
    # Parent of tools/ is context-foundry/
    # Parent of context-foundry/ is what we want
    cf_dir = Path(__file__).parent.parent.resolve()
    return cf_dir.parent




def _truncate_output(output: str, max_tokens: int = 20000) -> tuple[str, bool, dict]:
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

    lines = output.split('\n')
    total_lines = len(lines)
    total_chars = len(output)

    # If output is small enough, return as-is
    if total_chars <= max_chars:
        return output, False, {
            "total_lines": total_lines,
            "total_chars": total_chars
        }

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
    start_section = '\n'.join(lines[:start_line_idx])
    end_section = '\n'.join(lines[end_line_idx:])

    truncated_lines = end_line_idx - start_line_idx
    truncation_message = f"\n\n{'='*60}\n[OUTPUT TRUNCATED]\nShowing: First {start_line_idx} lines + Last {len(lines) - end_line_idx} lines\nHidden: {truncated_lines} lines ({total_chars - len(start_section) - len(end_section):,} chars)\nTotal: {total_lines:,} lines ({total_chars:,} chars)\n{'='*60}\n\n"

    truncated_output = start_section + truncation_message + end_section

    return truncated_output, True, {
        "total_lines": total_lines,
        "total_chars": total_chars,
        "truncated_lines": truncated_lines,
        "kept_start_lines": start_line_idx,
        "kept_end_lines": len(lines) - end_line_idx
    }


@mcp.tool()
def context_foundry_status() -> str:
    """
    Get the current status of Context Foundry.

    Returns:
        Status information including version and capabilities
    """
    return """Context Foundry MCP Server - Status

✅ Server: Running
✅ Version: 1.0.0

**Available Tools:**

🚀 **Autonomous Build & Deploy:**
- autonomous_build_and_deploy: Fully autonomous Scout→Architect→Builder→Test→Deploy workflow
  Runs in background with self-healing test loop and GitHub deployment

🔄 **Task Delegation:**
- delegate_to_claude_code: Delegate tasks to fresh Claude Code instances (synchronous)
- delegate_to_claude_code_async: Delegate tasks asynchronously (parallel execution)
- get_delegation_result: Check status and retrieve results of async tasks
- list_delegations: List all active and completed async tasks

📊 **Pattern Management:**
- read_global_patterns: Read patterns from global pattern storage
- save_global_patterns: Save patterns to global pattern storage
- merge_project_patterns: Merge project patterns into global storage
- migrate_all_project_patterns: Migrate all project patterns to global storage

ℹ️  **Status:**
- context_foundry_status: This status message

**Usage:**
All tools work with both Claude Desktop and Claude Code CLI without requiring API keys.
The autonomous build system inherits your Claude authentication automatically.
"""


@mcp.tool()
def delegate_to_claude_code(
    task: str,
    working_directory: Optional[str] = None,
    timeout_minutes: float = 10.0,
    additional_flags: Optional[str] = None,
    include_full_output: bool = False
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
    try:
        # Build the command
        # Use --print flag to run in non-interactive mode and exit after completion
        # Use --permission-mode bypassPermissions to skip all permission prompts
        # Use --strict-mcp-config to prevent spawned instance from loading MCP servers (avoids recursion)
        # Disable thinking mode to prevent thinking blocks in output
        cmd = ["claude", "--print", "--permission-mode", "bypassPermissions", "--strict-mcp-config", "--settings", '{"thinkingMode": "off"}']

        # Add additional flags if provided
        if additional_flags:
            # Split flags by spaces, handling quoted strings
            import shlex
            flags = shlex.split(additional_flags)
            cmd.extend(flags)

        # Add the task as the final argument
        cmd.append(task)

        # Determine working directory
        cwd = working_directory if working_directory else os.getcwd()

        # Validate working directory exists
        if not os.path.isdir(cwd):
            return f"""❌ Error: Working directory does not exist

Directory: {cwd}

Please provide a valid directory path or omit the working_directory parameter to use the current directory.
"""

        # Convert timeout to seconds
        timeout_seconds = timeout_minutes * 60

        # Start timer
        start_time = time.time()

        # Execute claude
        # stdin=DEVNULL prevents subprocess from waiting for input
        # env ensures PATH and other variables are properly set
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            stdin=subprocess.DEVNULL,
            env={
                **os.environ,  # Inherit current environment including PATH
                'PYTHONUNBUFFERED': '1',  # Disable Python output buffering
            }
        )

        # Calculate duration
        duration = time.time() - start_time
        duration_formatted = f"{duration:.2f} seconds"

        # Format the output
        status_emoji = "✅" if result.returncode == 0 else "❌"
        status_text = "Success" if result.returncode == 0 else f"Failed (exit code: {result.returncode})"

        # Apply output truncation if requested
        if include_full_output:
            stdout_display = result.stdout if result.stdout else "(empty)"
            stderr_display = result.stderr if result.stderr else "(empty)"
            truncation_notice = ""
        else:
            stdout_truncated, stdout_was_truncated, stdout_stats = _truncate_output(result.stdout or "", max_tokens=10000)
            stderr_truncated, stderr_was_truncated, stderr_stats = _truncate_output(result.stderr or "", max_tokens=10000)

            stdout_display = stdout_truncated if stdout_truncated else "(empty)"
            stderr_display = stderr_truncated if stderr_truncated else "(empty)"

            # Add truncation notice if either was truncated
            if stdout_was_truncated or stderr_was_truncated:
                truncation_notice = "\n⚠️  **Output Truncated**: Large outputs have been truncated to stay under token limits.\n   Use `include_full_output=True` parameter to see complete output.\n"
            else:
                truncation_notice = ""

        output = f"""{status_emoji} Claude Code Delegation {status_text}
{truncation_notice}
**Task:** {task}
**Working Directory:** {cwd}
**Duration:** {duration_formatted}
**Command:** {' '.join(cmd)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 STDOUT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{stdout_display}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📥 STDERR:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{stderr_display}
"""
        return output

    except subprocess.TimeoutExpired:
        duration = timeout_minutes
        return f"""⏱️ Claude Code Delegation Timeout

**Task:** {task}
**Working Directory:** {cwd}
**Timeout Limit:** {timeout_minutes} minutes

The claude process exceeded the timeout limit and was terminated.

**Suggestions:**
1. Increase the timeout_minutes parameter for longer tasks
2. Break the task into smaller sub-tasks
3. Check if the task is stuck or waiting for input
"""

    except FileNotFoundError:
        return f"""❌ Error: claude command not found

The 'claude' CLI executable is not in your PATH.

**Installation:**
1. Make sure Claude Code CLI is installed
2. Add it to your PATH environment variable
3. Verify installation: `which claude` or `claude --version`

**Current PATH:** {os.environ.get('PATH', 'not set')}
**Current Working Directory:** {cwd}
"""

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return f"""❌ Error during claude delegation

**Task:** {task}
**Error:** {str(e)}

**Traceback:**
{error_details}

**Debug Info:**
- Working Directory: {cwd}
- Command: {' '.join(cmd) if 'cmd' in locals() else 'N/A'}
"""


@mcp.tool()
def delegate_to_claude_code_async(
    task: str,
    working_directory: Optional[str] = None,
    timeout_minutes: float = 10.0,
    additional_flags: Optional[str] = None
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
    try:
        # Build the command with thinking disabled
        cmd = ["claude", "--print", "--permission-mode", "bypassPermissions", "--strict-mcp-config", "--settings", '{"thinkingMode": "off"}']

        # Add additional flags if provided
        if additional_flags:
            import shlex
            flags = shlex.split(additional_flags)
            cmd.extend(flags)

        # Add the task
        cmd.append(task)

        # Determine working directory
        cwd = working_directory if working_directory else os.getcwd()

        # Validate working directory exists
        if not os.path.isdir(cwd):
            return json.dumps({
                "error": f"Working directory does not exist: {cwd}",
                "task_id": None,
                "status": "failed"
            })

        # Generate unique task ID
        task_id = str(uuid.uuid4())

        # Start the process (non-blocking)
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            env={
                **os.environ,
                'PYTHONUNBUFFERED': '1',
            }
        )

        # Store task info
        active_tasks[task_id] = {
            "process": process,
            "cmd": cmd,
            "cwd": cwd,
            "task": task,
            "start_time": datetime.now(),
            "timeout_minutes": timeout_minutes,
            "status": "running",
            "result": None,
            "stdout": None,
            "stderr": None,
            "duration": None,
        }

        return json.dumps({
            "task_id": task_id,
            "status": "started",
            "task": task,
            "working_directory": cwd,
            "timeout_minutes": timeout_minutes,
            "message": f"Task started successfully. Use get_delegation_result('{task_id}') to check status and retrieve results."
        }, indent=2)

    except Exception as e:
        import traceback
        return json.dumps({
            "error": str(e),
            "traceback": traceback.format_exc(),
            "task_id": None,
            "status": "failed"
        }, indent=2)


@mcp.tool()
def get_delegation_result(task_id: str, include_full_output: bool = False) -> str:
    """
    Get the status and results of an async delegation task.

    Args:
        task_id: The task ID returned from delegate_to_claude_code_async()
        include_full_output: If False (default), truncate large outputs to stay under token limits.
                            If True, return complete stdout/stderr regardless of size.

    Returns:
        JSON string with task status and results (if complete, with truncated output by default)

    Examples:
        # Check task status
        result = get_delegation_result("abc-123-def-456")

        # If complete, result contains stdout/stderr (truncated by default)
        # If still running, shows elapsed time
        # If failed, shows error details

        # Get full output (may exceed token limits for large builds)
        result = get_delegation_result("abc-123-def-456", include_full_output=True)
    """
    try:
        # Check if task exists
        if task_id not in active_tasks:
            return json.dumps({
                "task_id": task_id,
                "status": "not_found",
                "error": f"Task ID '{task_id}' not found. Use list_delegations() to see active tasks."
            }, indent=2)

        task_info = active_tasks[task_id]
        process = task_info["process"]

        # Check if process is still running
        poll_result = process.poll()

        if poll_result is None:
            # Still running
            elapsed = (datetime.now() - task_info["start_time"]).total_seconds()
            timeout_seconds = task_info["timeout_minutes"] * 60

            # Check for timeout
            if elapsed > timeout_seconds:
                # Kill the process
                process.kill()
                process.wait()
                task_info["status"] = "timeout"
                task_info["duration"] = elapsed

                timeout_result = {
                    "task_id": task_id,
                    "status": "timeout",
                    "elapsed_seconds": elapsed,
                    "timeout_minutes": task_info["timeout_minutes"],
                    "message": f"Task exceeded timeout of {task_info['timeout_minutes']} minutes and was terminated."
                }

                return json.dumps(timeout_result, indent=2)

            # Still running within timeout
            # Try to read phase information
            phase_info = _read_phase_info(task_info["cwd"])

            result = {
                "task_id": task_id,
                "status": "running",
                "elapsed_seconds": round(elapsed, 2),
                "timeout_minutes": task_info["timeout_minutes"],
                "progress": f"{round((elapsed / timeout_seconds) * 100, 1)}% of timeout elapsed"
            }

            # Add phase information if available
            if phase_info:
                result["current_phase"] = phase_info.get("current_phase", "Unknown")
                result["phase_number"] = phase_info.get("phase_number", "?/7")
                result["phase_status"] = phase_info.get("status", "unknown")
                result["progress_detail"] = phase_info.get("progress_detail", "Working...")
                result["test_iteration"] = phase_info.get("test_iteration", 0)
                result["phases_completed"] = phase_info.get("phases_completed", [])

            return json.dumps(result, indent=2)

        # Process completed - capture output if not already captured
        if task_info["result"] is None:
            # Don't use communicate() if stdin was already closed
            # Just read remaining output from pipes
            try:
                stdout = process.stdout.read() if process.stdout else ""
                stderr = process.stderr.read() if process.stderr else ""
            except Exception as e:
                stdout = f"Error reading stdout: {e}"
                stderr = f"Error reading stderr: {e}"
            elapsed = (datetime.now() - task_info["start_time"]).total_seconds()

            task_info["stdout"] = stdout
            task_info["stderr"] = stderr
            task_info["duration"] = elapsed
            task_info["exit_code"] = process.returncode
            task_info["status"] = "completed" if process.returncode == 0 else "failed"

            # ============================================================================
            # AUTOMATIC PATTERN MERGE FOR AUTONOMOUS BUILDS
            # ============================================================================
            # If this was an autonomous build that completed successfully, automatically
            # merge patterns from local feedback file to global pattern storage
            is_autonomous_build = task_info.get("build_type") == "autonomous"
            build_successful = process.returncode == 0

            if is_autonomous_build and build_successful:
                try:
                    # Look for feedback file in .context-foundry/feedback/
                    feedback_dir = Path(task_info["cwd"]) / ".context-foundry" / "feedback"
                    if feedback_dir.exists():
                        # Find the most recent build-feedback file
                        feedback_files = list(feedback_dir.glob("build-feedback-*.json"))
                        if feedback_files:
                            # Sort by modification time, get most recent
                            latest_feedback = max(feedback_files, key=lambda p: p.stat().st_mtime)

                            # Call merge_project_patterns to save learnings to global database
                            merge_result_str = merge_project_patterns(
                                project_pattern_file=str(latest_feedback),
                                pattern_type="common-issues",
                                increment_build_count=True
                            )

                            # Parse result to check success
                            merge_result = json.loads(merge_result_str)
                            if merge_result.get("status") == "success":
                                stats = merge_result.get("merge_stats", {})
                                print(f"\n✅ Patterns merged to global database:")
                                print(f"   New patterns: {stats.get('new_patterns', 0)}")
                                print(f"   Updated patterns: {stats.get('updated_patterns', 0)}")
                                print(f"   Global pattern file: {merge_result.get('global_file', 'unknown')}")

                                # Store merge result in task info for reporting
                                task_info["pattern_merge_result"] = merge_result
                            else:
                                print(f"\n⚠️  Pattern merge failed: {merge_result.get('error', 'unknown error')}")
                                task_info["pattern_merge_error"] = merge_result.get("error")

                except Exception as e:
                    # Pattern merge failure should not break the build result
                    # Just log the error and continue
                    print(f"\n⚠️  Pattern merge exception (non-critical): {e}")
                    task_info["pattern_merge_error"] = str(e)

        # Format result with optional output truncation
        if include_full_output:
            # Return full output regardless of size
            stdout_display = task_info["stdout"] or "(empty)"
            stderr_display = task_info["stderr"] or "(empty)"
            result = {
                "task_id": task_id,
                "status": task_info["status"],
                "task": task_info["task"],
                "working_directory": task_info["cwd"],
                "duration_seconds": round(task_info["duration"], 2),
                "exit_code": task_info["exit_code"],
                "command": " ".join(task_info["cmd"]),
                "stdout": stdout_display,
                "stderr": stderr_display,
                "output_truncated": False
            }
        else:
            # Apply truncation to stay under token limits
            stdout_truncated, stdout_was_truncated, stdout_stats = _truncate_output(task_info["stdout"] or "", max_tokens=10000)
            stderr_truncated, stderr_was_truncated, stderr_stats = _truncate_output(task_info["stderr"] or "", max_tokens=10000)

            result = {
                "task_id": task_id,
                "status": task_info["status"],
                "task": task_info["task"],
                "working_directory": task_info["cwd"],
                "duration_seconds": round(task_info["duration"], 2),
                "exit_code": task_info["exit_code"],
                "command": " ".join(task_info["cmd"]),
                "stdout": stdout_truncated or "(empty)",
                "stderr": stderr_truncated or "(empty)",
                "output_truncated": stdout_was_truncated or stderr_was_truncated
            }

            # Add stats if any truncation occurred
            if stdout_was_truncated or stderr_was_truncated:
                result["truncation_info"] = {
                    "message": "Output truncated to stay under token limits. Use include_full_output=True to see complete output.",
                    "stdout_stats": stdout_stats if stdout_was_truncated else None,
                    "stderr_stats": stderr_stats if stderr_was_truncated else None
                }

        return json.dumps(result, indent=2)

    except Exception as e:
        import traceback
        return json.dumps({
            "task_id": task_id,
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }, indent=2)


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
    try:
        if not active_tasks:
            return json.dumps({
                "message": "No active delegation tasks",
                "tasks": []
            }, indent=2)

        tasks_list = []

        for task_id, task_info in active_tasks.items():
            process = task_info["process"]
            poll_result = process.poll()

            elapsed = (datetime.now() - task_info["start_time"]).total_seconds()

            # Update status if needed
            if poll_result is None:
                status = "running"
            elif task_info["result"] is None:
                # Process finished but results not retrieved yet
                status = "completed (not retrieved)"
            else:
                status = task_info["status"]

            tasks_list.append({
                "task_id": task_id,
                "status": status,
                "task": task_info["task"][:80] + "..." if len(task_info["task"]) > 80 else task_info["task"],
                "elapsed_seconds": round(elapsed, 2),
                "timeout_minutes": task_info["timeout_minutes"],
                "working_directory": task_info["cwd"]
            })

        return json.dumps({
            "total_tasks": len(tasks_list),
            "tasks": tasks_list,
            "message": f"Use get_delegation_result(task_id) to retrieve results"
        }, indent=2)

    except Exception as e:
        import traceback
        return json.dumps({
            "error": str(e),
            "traceback": traceback.format_exc()
        }, indent=2)


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
    use_parallel: bool = True,
    incremental: bool = False,
    force_rebuild: bool = False
) -> str:
    """
    Fully autonomous build/test/fix/deploy with self-healing test loop.

    **EXECUTION MODE (CURRENT):**
    - Uses orchestrator_prompt.txt with /agents command
    - Inherits Claude Code authentication (no API keys needed)
    - Supports parallel execution via bash process spawning:
      • Phase 2.5: Parallel Builders (2-8 concurrent based on project size)
      • Phase 4.5: Parallel Tests (unit/E2E/lint run simultaneously)
    - **30-45% faster than pure sequential execution**
    - See: docs/PARALLEL_AGENTS_ARCHITECTURE.md

    **OLD PYTHON SYSTEM (DEPRECATED):**
    - use_parallel=True now auto-corrects to False
    - Old system required API keys and external dependencies
    - Removed to eliminate confusion and dependency issues

    Spawns fresh Claude instance that runs in the BACKGROUND:
    - Creates Scout/Architect/Builder/Tester agents
    - Implements complete project autonomously
    - Tests automatically
    - If tests fail: Goes back to Architect → Builder → Test (up to max_test_iterations)
    - If tests pass: Deploys to GitHub
    - Zero human intervention required

    **NON-BLOCKING EXECUTION:**
    - Starts the build immediately
    - Returns task_id right away
    - Build runs in background while you continue working
    - Use get_delegation_result(task_id) to check status
    - Use list_delegations() to see all running builds

    Args:
        task: What to build/fix/enhance
        working_directory: Where to work
        github_repo_name: Create new repo (optional)
        existing_repo: Fix/enhance existing (optional)
        mode: "new_project", "fix_bugs", "add_docs"
        enable_test_loop: Enable self-healing test loop (default: True)
        max_test_iterations: Max test/fix cycles (default: 3)
        timeout_minutes: Max execution time (default: 90)
        use_parallel: Use parallel execution (default: True, ~45% faster)
        incremental: Enable incremental builds (default: False, 70-90% faster on rebuilds)
        force_rebuild: Force full rebuild even if incremental enabled (default: False)

    Returns:
        JSON with task_id and status (returns immediately)

    Examples:
        # Start build in background
        result = autonomous_build_and_deploy(
            task="Build weather app with OpenWeatherMap API",
            working_directory="/tmp/weather-app",
            github_repo_name="weather-app",
            enable_test_loop=True
        )
        # Returns: {"task_id": "abc-123", "status": "started", ...}

        # Continue working while build runs...

        # Check status later
        status = get_delegation_result("abc-123")

        # List all builds
        all_builds = list_delegations()
    """
    try:
        # Determine final working directory FIRST (needed for both modes)
        working_dir_input = Path(working_directory)
        if working_dir_input.is_absolute():
            final_working_dir = working_dir_input
        else:
            cf_parent = _get_context_foundry_parent_dir()
            final_working_dir = cf_parent / working_directory

        final_working_dir_str = str(final_working_dir)

        # Validate/create working directory
        if not final_working_dir.exists():
            final_working_dir.mkdir(parents=True, exist_ok=True)

        # Extract project name for display
        project_name = github_repo_name or final_working_dir.name

        # HARD BLOCK: Old Python parallel system is DEPRECATED and REMOVED
        # It required API keys in .env and doesn't inherit Claude Code's auth.
        # Always use the new /agents-based orchestrator instead.
        if use_parallel:
            error_msg = """
❌ ERROR: use_parallel=True is DEPRECATED and DISABLED

The old Python parallel system has been removed because:
  • Required API keys in .env (doesn't inherit Claude Code auth)
  • Had external dependencies (openai package)
  • Superseded by new /agents-based parallel system

The /agents system (use_parallel=False) DOES support parallel execution:
  • Phase 2.5: Parallel Builders (2-8 concurrent agents via bash)
  • Phase 4.5: Parallel Tests (unit/E2E/lint simultaneously)
  • See: docs/PARALLEL_AGENTS_ARCHITECTURE.md

Auto-correcting to use_parallel=False...
"""
            print(error_msg, file=sys.stderr)
            use_parallel = False  # Force correction

        # NEW /agents-based system with orchestrator_prompt.txt
        # This system DOES support parallel execution via bash process spawning:
        # - Phase 2.5: Parallel Builders (2-8 concurrent)
        # - Phase 4.5: Parallel Tests (unit/E2E/lint concurrent)
        print(f"✅ Using /agents-based orchestrator (supports parallel execution)", file=sys.stderr)
        print(f"   See docs/PARALLEL_AGENTS_ARCHITECTURE.md for details\n", file=sys.stderr)

        # Create orchestrator task configuration with resolved path
        task_config = {
            "task": task,
            "working_directory": final_working_dir_str,
            "github_repo_name": github_repo_name,
            "existing_repo": existing_repo,
            "mode": mode,
            "enable_test_loop": enable_test_loop,
            "max_test_iterations": max_test_iterations
        }

        # Load orchestrator system prompt
        orchestrator_prompt_path = Path(__file__).parent / "orchestrator_prompt.txt"
        if not orchestrator_prompt_path.exists():
            return json.dumps({
                "status": "error",
                "error": f"Orchestrator prompt not found at {orchestrator_prompt_path}. Please create tools/orchestrator_prompt.txt"
            }, indent=2)

        with open(orchestrator_prompt_path) as f:
            system_prompt = f.read()

        # Build task prompt
        task_prompt = f"""AUTONOMOUS BUILD TASK

CONFIGURATION:
{json.dumps(task_config, indent=2)}

Execute the full Scout → Architect → Builder → Test → Deploy workflow.
{"Self-healing test loop is ENABLED. Fix and retry up to " + str(max_test_iterations) + " times if tests fail." if enable_test_loop else "Test loop is DISABLED. Test once and proceed."}

Return JSON summary when complete.
BEGIN AUTONOMOUS EXECUTION NOW.
"""

        # Build command with thinking disabled
        cmd = [
            "claude", "--print",
            "--permission-mode", "bypassPermissions",
            "--strict-mcp-config",
            "--settings", '{"thinkingMode": "off"}',
            "--system-prompt", system_prompt,
            task_prompt
        ]

        # Generate unique task ID
        task_id = str(uuid.uuid4())

        # Start the process (NON-BLOCKING)
        process = subprocess.Popen(
            cmd,
            cwd=final_working_dir_str,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            env={
                **os.environ,
                'PYTHONUNBUFFERED': '1',
            }
        )

        # Store task info
        active_tasks[task_id] = {
            "process": process,
            "cmd": cmd,
            "cwd": final_working_dir_str,
            "task": task,
            "start_time": datetime.now(),
            "timeout_minutes": timeout_minutes,
            "status": "running",
            "result": None,
            "stdout": None,
            "stderr": None,
            "duration": None,
            "task_config": task_config,
            "build_type": "autonomous"  # Mark as autonomous build for special handling
        }

        return json.dumps({
            "task_id": task_id,
            "status": "started",
            "project": project_name,
            "task_summary": task[:100] + ("..." if len(task) > 100 else ""),
            "working_directory": final_working_dir_str,
            "github_repo": github_repo_name,
            "timeout_minutes": timeout_minutes,
            "enable_test_loop": enable_test_loop,
            "message": f"""
🚀 Autonomous build started!

Project: {project_name}
Task ID: {task_id}
Location: {final_working_dir_str}
Expected duration: 7-15 minutes

You can continue working - the build runs in the background.

Check status anytime:
  • Ask: "What's the status of task {task_id}?"
  • Or use: get_delegation_result("{task_id}")

List all builds:
  • Ask: "Show all my builds"
  • Or use: list_delegations()

I'll notify you when it's complete!
""".strip()
        }, indent=2)

    except Exception as e:
        import traceback
        # Try to use final_working_dir if available, otherwise use original input
        error_working_dir = final_working_dir_str if 'final_working_dir_str' in locals() else working_directory
        return json.dumps({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "task": task,
            "working_directory": error_working_dir
        }, indent=2)


# ============================================================================
# Global Pattern Sharing Functions
# ============================================================================


@mcp.tool()
def read_global_patterns(pattern_type: str = "common-issues") -> str:
    """
    Read global patterns from ~/.context-foundry/patterns/

    Args:
        pattern_type: Type of patterns to read ("common-issues", "scout-learnings", "build-metrics")

    Returns:
        JSON string with patterns or error message

    Examples:
        # Read common issues
        patterns = read_global_patterns("common-issues")

        # Read scout learnings
        learnings = read_global_patterns("scout-learnings")
    """
    try:
        # Global pattern directory
        global_pattern_dir = Path.home() / ".context-foundry" / "patterns"

        # Pattern file mapping
        pattern_files = {
            "common-issues": "common-issues.json",
            "scout-learnings": "scout-learnings.json",
            "build-metrics": "build-metrics.json"
        }

        if pattern_type not in pattern_files:
            return json.dumps({
                "status": "error",
                "error": f"Invalid pattern_type: {pattern_type}",
                "valid_types": list(pattern_files.keys())
            }, indent=2)

        pattern_file = global_pattern_dir / pattern_files[pattern_type]

        # Create directory if it doesn't exist
        if not global_pattern_dir.exists():
            global_pattern_dir.mkdir(parents=True, exist_ok=True)

        # If file doesn't exist, return empty structure
        if not pattern_file.exists():
            if pattern_type == "common-issues":
                default_data = {
                    "patterns": [],
                    "version": "1.0",
                    "last_updated": datetime.now().isoformat(),
                    "total_builds": 0
                }
            elif pattern_type == "scout-learnings":
                default_data = {
                    "learnings": [],
                    "version": "1.0",
                    "last_updated": datetime.now().isoformat()
                }
            elif pattern_type == "build-metrics":
                default_data = {
                    "metrics": [],
                    "version": "1.0",
                    "last_updated": datetime.now().isoformat()
                }

            return json.dumps({
                "status": "success",
                "message": f"No existing {pattern_type} found, returning empty structure",
                "data": default_data,
                "file_path": str(pattern_file)
            }, indent=2)

        # Read existing patterns
        with open(pattern_file, 'r') as f:
            data = json.load(f)

        return json.dumps({
            "status": "success",
            "data": data,
            "file_path": str(pattern_file),
            "last_updated": data.get("last_updated", "unknown")
        }, indent=2)

    except json.JSONDecodeError as e:
        return json.dumps({
            "status": "error",
            "error": f"Invalid JSON in pattern file: {str(e)}",
            "file_path": str(pattern_file)
        }, indent=2)

    except Exception as e:
        import traceback
        return json.dumps({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }, indent=2)


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
        try:
            data = json.loads(patterns_data)
        except json.JSONDecodeError as e:
            return json.dumps({
                "status": "error",
                "error": f"Invalid JSON in patterns_data: {str(e)}"
            }, indent=2)

        # Global pattern directory
        global_pattern_dir = Path.home() / ".context-foundry" / "patterns"
        global_pattern_dir.mkdir(parents=True, exist_ok=True)

        # Pattern file mapping
        pattern_files = {
            "common-issues": "common-issues.json",
            "scout-learnings": "scout-learnings.json",
            "build-metrics": "build-metrics.json"
        }

        if pattern_type not in pattern_files:
            return json.dumps({
                "status": "error",
                "error": f"Invalid pattern_type: {pattern_type}",
                "valid_types": list(pattern_files.keys())
            }, indent=2)

        pattern_file = global_pattern_dir / pattern_files[pattern_type]

        # Update last_updated timestamp
        data["last_updated"] = datetime.now().isoformat()

        # Write to file
        with open(pattern_file, 'w') as f:
            json.dump(data, f, indent=2)

        # Get count of items
        if pattern_type == "common-issues":
            count = len(data.get("patterns", []))
        elif pattern_type == "scout-learnings":
            count = len(data.get("learnings", []))
        elif pattern_type == "build-metrics":
            count = len(data.get("metrics", []))

        return json.dumps({
            "status": "success",
            "message": f"Saved {count} {pattern_type} to global storage",
            "file_path": str(pattern_file),
            "last_updated": data["last_updated"]
        }, indent=2)

    except Exception as e:
        import traceback
        return json.dumps({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }, indent=2)


@mcp.tool()
def merge_project_patterns(
    project_pattern_file: str,
    pattern_type: str = "common-issues",
    increment_build_count: bool = True
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
    try:
        # Read project patterns
        project_file_path = Path(project_pattern_file)
        if not project_file_path.exists():
            return json.dumps({
                "status": "error",
                "error": f"Project pattern file not found: {project_pattern_file}"
            }, indent=2)

        with open(project_file_path, 'r') as f:
            project_data = json.load(f)

        # Read global patterns
        global_result = read_global_patterns(pattern_type)
        global_response = json.loads(global_result)

        if global_response["status"] != "success":
            return json.dumps({
                "status": "error",
                "error": "Failed to read global patterns",
                "details": global_response
            }, indent=2)

        global_data = global_response["data"]

        # Merge logic
        merge_stats = {
            "new_patterns": 0,
            "updated_patterns": 0,
            "total_project_patterns": 0
        }

        if pattern_type == "common-issues":
            # Get patterns arrays
            project_patterns = project_data.get("patterns", [])
            global_patterns = global_data.get("patterns", [])
            merge_stats["total_project_patterns"] = len(project_patterns)

            # Create lookup by pattern_id
            global_by_id = {p["pattern_id"]: i for i, p in enumerate(global_patterns)}

            # Merge each project pattern
            for proj_pattern in project_patterns:
                pattern_id = proj_pattern.get("pattern_id")

                if pattern_id in global_by_id:
                    # Update existing pattern
                    idx = global_by_id[pattern_id]
                    existing = global_patterns[idx]

                    # Increment frequency
                    existing["frequency"] = existing.get("frequency", 1) + 1

                    # Update last_seen
                    existing["last_seen"] = datetime.now().strftime("%Y-%m-%d")

                    # Merge project_types (unique values)
                    existing_types = set(existing.get("project_types", []))
                    new_types = set(proj_pattern.get("project_types", []))
                    existing["project_types"] = sorted(list(existing_types | new_types))

                    # Preserve highest severity
                    severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
                    existing_severity = severity_order.get(existing.get("severity", "LOW"), 1)
                    new_severity = severity_order.get(proj_pattern.get("severity", "LOW"), 1)
                    if new_severity > existing_severity:
                        existing["severity"] = proj_pattern["severity"]

                    # Merge solutions (keep more comprehensive)
                    existing_solution = existing.get("solution", {})
                    new_solution = proj_pattern.get("solution", {})
                    for key, value in new_solution.items():
                        if key not in existing_solution or len(value) > len(existing_solution.get(key, "")):
                            existing_solution[key] = value
                    existing["solution"] = existing_solution

                    merge_stats["updated_patterns"] += 1
                else:
                    # Add new pattern
                    new_pattern = proj_pattern.copy()
                    new_pattern["first_seen"] = datetime.now().strftime("%Y-%m-%d")
                    new_pattern["last_seen"] = datetime.now().strftime("%Y-%m-%d")
                    new_pattern["frequency"] = 1
                    global_patterns.append(new_pattern)
                    merge_stats["new_patterns"] += 1

            global_data["patterns"] = global_patterns

            # Increment build count
            if increment_build_count:
                global_data["total_builds"] = global_data.get("total_builds", 0) + 1

        elif pattern_type == "scout-learnings":
            # Similar logic for scout learnings
            project_learnings = project_data.get("learnings", [])
            global_learnings = global_data.get("learnings", [])
            merge_stats["total_project_patterns"] = len(project_learnings)

            # Create lookup by learning_id
            global_by_id = {l["learning_id"]: i for i, l in enumerate(global_learnings)}

            for proj_learning in project_learnings:
                learning_id = proj_learning.get("learning_id")

                if learning_id in global_by_id:
                    # Update existing learning
                    idx = global_by_id[learning_id]
                    existing = global_learnings[idx]

                    # Merge project types
                    existing_types = set(existing.get("project_types", []))
                    new_types = set(proj_learning.get("project_types", []))
                    existing["project_types"] = sorted(list(existing_types | new_types))

                    # Merge key points (unique values)
                    existing_points = set(existing.get("key_points", []))
                    new_points = set(proj_learning.get("key_points", []))
                    existing["key_points"] = sorted(list(existing_points | new_points))

                    merge_stats["updated_patterns"] += 1
                else:
                    # Add new learning
                    new_learning = proj_learning.copy()
                    new_learning["first_seen"] = datetime.now().strftime("%Y-%m-%d")
                    global_learnings.append(new_learning)
                    merge_stats["new_patterns"] += 1

            global_data["learnings"] = global_learnings

        # Save merged patterns
        save_result = save_global_patterns(pattern_type, json.dumps(global_data))
        save_response = json.loads(save_result)

        if save_response["status"] != "success":
            return json.dumps({
                "status": "error",
                "error": "Failed to save merged patterns",
                "details": save_response
            }, indent=2)

        return json.dumps({
            "status": "success",
            "message": f"Successfully merged {pattern_type} from project",
            "merge_stats": merge_stats,
            "global_file": save_response["file_path"],
            "project_file": str(project_file_path)
        }, indent=2)

    except json.JSONDecodeError as e:
        return json.dumps({
            "status": "error",
            "error": f"Invalid JSON in pattern file: {str(e)}",
            "file_path": project_pattern_file
        }, indent=2)

    except Exception as e:
        import traceback
        return json.dumps({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }, indent=2)


@mcp.tool()
def migrate_all_project_patterns(projects_base_dir: str) -> str:
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
    try:
        base_path = Path(projects_base_dir)
        if not base_path.exists():
            return json.dumps({
                "status": "error",
                "error": f"Directory not found: {projects_base_dir}"
            }, indent=2)

        # Find all project pattern directories
        pattern_dirs = []
        for project_dir in base_path.iterdir():
            if project_dir.is_dir():
                pattern_dir = project_dir / ".context-foundry" / "patterns"
                if pattern_dir.exists():
                    pattern_dirs.append({
                        "project": project_dir.name,
                        "path": pattern_dir
                    })

        if not pattern_dirs:
            return json.dumps({
                "status": "success",
                "message": "No project patterns found to migrate",
                "projects_scanned": len(list(base_path.iterdir()))
            }, indent=2)

        # Migrate each project
        migration_results = {
            "projects_migrated": 0,
            "total_patterns_merged": 0,
            "errors": []
        }

        for proj_info in pattern_dirs:
            project_name = proj_info["project"]
            pattern_dir = proj_info["path"]

            # Migrate common-issues.json if it exists
            common_issues_file = pattern_dir / "common-issues.json"
            if common_issues_file.exists():
                result = merge_project_patterns(
                    str(common_issues_file),
                    "common-issues",
                    increment_build_count=False  # Don't increment for migration
                )
                result_data = json.loads(result)
                if result_data["status"] == "success":
                    migration_results["total_patterns_merged"] += result_data["merge_stats"]["new_patterns"]
                    migration_results["total_patterns_merged"] += result_data["merge_stats"]["updated_patterns"]
                else:
                    migration_results["errors"].append({
                        "project": project_name,
                        "file": "common-issues.json",
                        "error": result_data.get("error", "Unknown error")
                    })

            # Migrate scout-learnings.json if it exists
            scout_learnings_file = pattern_dir / "scout-learnings.json"
            if scout_learnings_file.exists():
                result = merge_project_patterns(
                    str(scout_learnings_file),
                    "scout-learnings",
                    increment_build_count=False
                )
                result_data = json.loads(result)
                if result_data["status"] == "success":
                    migration_results["total_patterns_merged"] += result_data["merge_stats"]["new_patterns"]
                    migration_results["total_patterns_merged"] += result_data["merge_stats"]["updated_patterns"]
                else:
                    migration_results["errors"].append({
                        "project": project_name,
                        "file": "scout-learnings.json",
                        "error": result_data.get("error", "Unknown error")
                    })

            migration_results["projects_migrated"] += 1

        return json.dumps({
            "status": "success",
            "message": f"Migrated patterns from {migration_results['projects_migrated']} projects",
            "migration_results": migration_results,
            "projects_found": len(pattern_dirs)
        }, indent=2)

    except Exception as e:
        import traceback
        return json.dumps({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }, indent=2)


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


if __name__ == "__main__":
    # Run the MCP server
    # This uses stdio transport which is standard for Claude Desktop
    print_banner(version="1.0.0")
    print("", file=sys.stderr)
    print("📋 Available tools:", file=sys.stderr)
    print("   - context_foundry_status: Get server status", file=sys.stderr)
    print("   - delegate_to_claude_code: Delegate tasks to fresh Claude instances (synchronous)", file=sys.stderr)
    print("   - delegate_to_claude_code_async: Delegate tasks asynchronously (parallel execution)", file=sys.stderr)
    print("   - get_delegation_result: Check status and get results of async tasks", file=sys.stderr)
    print("   - list_delegations: List all active and completed async tasks", file=sys.stderr)
    print("   - autonomous_build_and_deploy: Fully autonomous Scout→Architect→Builder→Test→Deploy (runs in background)", file=sys.stderr)
    print("   - read_global_patterns: Read patterns from global pattern storage", file=sys.stderr)
    print("   - save_global_patterns: Save patterns to global pattern storage", file=sys.stderr)
    print("   - merge_project_patterns: Merge project patterns into global storage", file=sys.stderr)
    print("   - migrate_all_project_patterns: Migrate all project patterns to global storage", file=sys.stderr)
    print("💡 Configure in Claude Desktop or Claude Code CLI to use this server!", file=sys.stderr)

    mcp.run()
