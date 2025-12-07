"""Delegation management utilities for Context Foundry MCP server.

Handles task delegation to fresh Claude Code instances, including sync/async execution,
task monitoring, cancellation, and output streaming.
"""

import json
import os
import re
import select
import shlex
import shutil
import subprocess
import sys
import time
import traceback
import uuid
import threading
import psutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Import conversation logger for transparent agent visibility
try:
    from tools.mcp_utils.conversation_logger import ConversationLogger
except ImportError:
    ConversationLogger = None


def _write_delegation_metadata(task_id: str, metadata: dict) -> None:
    """
    Write delegation metadata to shared disk location for cross-process visibility.

    Args:
        task_id: Unique task identifier
        metadata: Dict containing task info (status, working_directory, start_time, etc.)
    """
    try:
        # Create delegations directory in .context-foundry
        delegations_dir = Path.home() / ".context-foundry" / "delegations"
        delegations_dir.mkdir(parents=True, exist_ok=True)

        # Write metadata to task-specific file
        task_file = delegations_dir / f"task-{task_id}.json"
        task_file.write_text(json.dumps(metadata, indent=2))

    except Exception as e:
        # Don't crash if writing fails - just log to stderr
        print(f"Warning: Failed to write delegation metadata: {e}", file=sys.stderr)


def _write_full_output_to_file(
    working_directory: str, stdout: str, stderr: str, task_id: str
) -> str:
    """
    Write full stdout and stderr to a file in .context-foundry directory.

    Args:
        working_directory: Directory where build is running
        stdout: Full stdout string
        stderr: Full stderr string
        task_id: Task ID for filename

    Returns:
        Path to output file
    """
    try:
        # Create .context-foundry directory if it doesn't exist
        context_dir = Path(working_directory) / ".context-foundry"
        context_dir.mkdir(parents=True, exist_ok=True)

        # Write output to file
        output_file = context_dir / f"build-output-{task_id}.txt"

        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("STDOUT\n")
            f.write("=" * 80 + "\n\n")
            f.write(stdout or "(empty)\n")
            f.write("\n\n")
            f.write("=" * 80 + "\n")
            f.write("STDERR\n")
            f.write("=" * 80 + "\n\n")
            f.write(stderr or "(empty)\n")

        return str(output_file)

    except Exception as e:
        # If file writing fails, return error message instead of failing completely
        return f"Error writing output file: {e}"


def delegate_to_claude_code_impl(
    task: str,
    working_directory: Optional[str],
    timeout_minutes: float,
    additional_flags: Optional[str],
    include_full_output: bool,
    truncate_output_func,  # Function reference from mcp_server
) -> str:
    """
    Implementation of delegate_to_claude_code tool.

    Spawns a new claude-code process, passes it the task, waits for completion,
    and returns the output.

    Args:
        task: The task/prompt to give to the new Claude Code instance
        working_directory: Directory where claude-code should run (defaults to current directory)
        timeout_minutes: Maximum execution time in minutes (default: 10 minutes)
        additional_flags: Additional CLI flags as a string (e.g., "--model claude-sonnet-4")
        include_full_output: If False (default), truncate large outputs to stay under token limits
        truncate_output_func: Reference to _truncate_output function

    Returns:
        Formatted output with status, duration, stdout, and stderr (truncated if needed)
    """
    try:
        # Build the command
        # Use --print flag to run in non-interactive mode and exit after completion
        # Use --permission-mode bypassPermissions to skip all permission prompts
        # Use --strict-mcp-config to prevent spawned instance from loading MCP servers (avoids recursion)
        # Disable thinking mode to prevent thinking blocks in output
        cmd = [
            "claude",
            "--print",
            "--permission-mode",
            "bypassPermissions",
            "--strict-mcp-config",
            "--settings",
            '{"thinkingMode": "off"}',
        ]

        # Add additional flags if provided
        if additional_flags:
            # Split flags by spaces, handling quoted strings
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

        # Check if claude CLI is available
        if not shutil.which("claude"):
            error_msg = """❌ Error: Claude CLI not found in PATH

The delegation system requires the Claude CLI to be installed and available in PATH.

Installation:
  - Download from: https://claude.com/download
  - Ensure it's in your PATH after installation

Current PATH: {}

Troubleshooting:
  - Verify installation: run 'which claude' in terminal
  - Check PATH: echo $PATH
  - Restart terminal after installation
""".format(os.environ.get("PATH", "NOT SET"))
            return error_msg

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
                "PYTHONUNBUFFERED": "1",  # Disable Python output buffering
            },
        )

        # Calculate duration
        duration = time.time() - start_time
        duration_formatted = f"{duration:.2f} seconds"

        # Format the output
        status_emoji = "✅" if result.returncode == 0 else "❌"
        status_text = (
            "Success"
            if result.returncode == 0
            else f"Failed (exit code: {result.returncode})"
        )

        # Apply output truncation if requested
        if include_full_output:
            stdout_display = result.stdout if result.stdout else "(empty)"
            stderr_display = result.stderr if result.stderr else "(empty)"
            truncation_notice = ""
        else:
            stdout_truncated, stdout_was_truncated, stdout_stats = truncate_output_func(
                result.stdout or "", max_tokens=10000
            )
            stderr_truncated, stderr_was_truncated, stderr_stats = truncate_output_func(
                result.stderr or "", max_tokens=10000
            )

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
**Command:** {" ".join(cmd)}

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

**Current PATH:** {os.environ.get("PATH", "not set")}
**Current Working Directory:** {cwd}
"""

    except Exception as e:
        error_details = traceback.format_exc()
        return f"""❌ Error during claude delegation

**Task:** {task}
**Error:** {str(e)}

**Traceback:**
{error_details}

**Debug Info:**
- Working Directory: {cwd}
- Command: {" ".join(cmd) if "cmd" in locals() else "N/A"}
"""


def delegate_to_claude_code_async_impl(
    task: str,
    working_directory: Optional[str],
    timeout_minutes: float,
    additional_flags: Optional[str],
    active_tasks: Dict[str, Dict[str, Any]],  # Reference to global active_tasks
) -> str:
    """
    Implementation of delegate_to_claude_code_async tool.

    Starts a task immediately and returns a task ID. The task runs in the background.

    Args:
        task: The task/prompt to give to the new Claude Code instance
        working_directory: Directory where claude should run (defaults to current directory)
        timeout_minutes: Maximum execution time in minutes
        additional_flags: Additional CLI flags as a string
        active_tasks: Reference to active_tasks dict from mcp_server

    Returns:
        JSON string with task_id and status
    """
    try:
        # Build the command with thinking disabled
        cmd = [
            "claude",
            "--print",
            "--permission-mode",
            "bypassPermissions",
            "--strict-mcp-config",
            "--settings",
            '{"thinkingMode": "off"}',
        ]

        # Add additional flags if provided
        if additional_flags:
            flags = shlex.split(additional_flags)
            cmd.extend(flags)

        # Add the task
        cmd.append(task)

        # Determine working directory
        cwd = working_directory if working_directory else os.getcwd()

        # Validate working directory exists
        if not os.path.isdir(cwd):
            return json.dumps(
                {
                    "error": f"Working directory does not exist: {cwd}",
                    "task_id": None,
                    "status": "failed",
                }
            )

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
                "PYTHONUNBUFFERED": "1",
            },
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

        # Write delegation info to shared disk location for cross-process visibility
        _write_delegation_metadata(
            task_id,
            {
                "task_id": task_id,
                "status": "running",
                "task": task,
                "working_directory": cwd,
                "start_time": datetime.now().isoformat(),
                "timeout_minutes": timeout_minutes,
                "pid": process.pid,
            },
        )

        return json.dumps(
            {
                "task_id": task_id,
                "status": "started",
                "task": task,
                "working_directory": cwd,
                "timeout_minutes": timeout_minutes,
                "message": f"Task started successfully. Use get_delegation_result('{task_id}') to check status and retrieve results.",
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "task_id": None,
                "status": "failed",
            },
            indent=2,
        )


def delegate_to_claude_code_streaming_impl(
    task: str,
    working_directory: Optional[str],
    timeout_minutes: float,
    additional_flags: Optional[str],
    active_tasks: Dict[str, Dict[str, Any]],
    enable_conversation_logging: bool = True,
) -> str:
    """
    Implementation of streaming delegation with full conversation visibility.

    Uses --output-format stream-json to capture structured events including:
    - Assistant messages (what the agent is saying)
    - Tool use (every tool being called)
    - Tool results (outcomes of tool calls)
    - Errors and completions

    Events are written to:
    - .context-foundry/conversations/conversation-{task_id}.jsonl (structured)
    - .context-foundry/conversations/conversation-{task_id}.log (human-readable)

    Args:
        task: The task/prompt to give to the new Claude Code instance
        working_directory: Directory where claude should run (defaults to current directory)
        timeout_minutes: Maximum execution time in minutes
        additional_flags: Additional CLI flags as a string
        active_tasks: Reference to active_tasks dict from mcp_server
        enable_conversation_logging: If True, log conversation to files

    Returns:
        JSON string with task_id, status, and conversation_log paths
    """
    try:
        # Build command with stream-json for full visibility
        cmd = [
            "claude",
            "--print",
            "--output-format",
            "stream-json",  # KEY: Enables structured event output
            "--verbose",  # Additional diagnostic info
            "--permission-mode",
            "bypassPermissions",
            "--strict-mcp-config",
            "--settings",
            '{"thinkingMode": "off"}',
        ]

        # Add additional flags if provided
        if additional_flags:
            flags = shlex.split(additional_flags)
            cmd.extend(flags)

        # Add the task
        cmd.append(task)

        # Determine working directory
        cwd = working_directory if working_directory else os.getcwd()

        # Validate working directory exists
        if not os.path.isdir(cwd):
            return json.dumps(
                {
                    "error": f"Working directory does not exist: {cwd}",
                    "task_id": None,
                    "status": "failed",
                }
            )

        # Generate unique task ID
        task_id = str(uuid.uuid4())

        # Initialize conversation logger
        conversation_logger = None
        if enable_conversation_logging and ConversationLogger:
            conversation_logger = ConversationLogger(task_id, cwd)

        # Start the process (non-blocking)
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,  # Line buffered for real-time output
            env={
                **os.environ,
                "PYTHONUNBUFFERED": "1",
            },
        )

        # Store task info with conversation logger
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
            "conversation_logger": conversation_logger,
            "streaming_mode": True,  # Flag to indicate stream-json mode
        }

        # Start background thread to process streaming output
        if conversation_logger:

            def process_stream():
                """Background thread to process stream-json output"""
                for event in conversation_logger.stream_from_sync_process(process):
                    # Events are automatically logged to files
                    # Could also push to a queue for real-time monitoring
                    pass

            stream_thread = threading.Thread(target=process_stream, daemon=True)
            stream_thread.start()
            active_tasks[task_id]["stream_thread"] = stream_thread

        # Write delegation info to shared disk location
        metadata = {
            "task_id": task_id,
            "status": "running",
            "task": task,
            "working_directory": cwd,
            "start_time": datetime.now().isoformat(),
            "timeout_minutes": timeout_minutes,
            "pid": process.pid,
            "streaming_mode": True,
        }

        if conversation_logger:
            metadata["conversation_jsonl"] = str(conversation_logger.jsonl_file)
            metadata["conversation_log"] = str(conversation_logger.readable_file)

        _write_delegation_metadata(task_id, metadata)

        result = {
            "task_id": task_id,
            "status": "started",
            "task": task,
            "working_directory": cwd,
            "timeout_minutes": timeout_minutes,
            "streaming_mode": True,
            "message": f"Task started with conversation logging. Use get_delegation_result('{task_id}') to check status.",
        }

        if conversation_logger:
            result["conversation_logs"] = {
                "jsonl": str(conversation_logger.jsonl_file),
                "readable": str(conversation_logger.readable_file),
                "watch_command": f"tail -f {conversation_logger.readable_file}",
            }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps(
            {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "task_id": None,
                "status": "failed",
            },
            indent=2,
        )


def get_conversation_events_impl(
    task_id: str,
    active_tasks: Dict[str, Dict[str, Any]],
    event_type: Optional[str] = None,
    last_n: int = 50,
) -> str:
    """
    Get conversation events from a streaming delegation task.

    Args:
        task_id: The task ID to get events for
        active_tasks: Reference to active_tasks dict from mcp_server
        event_type: Filter by event type (e.g., "tool_use", "assistant")
        last_n: Number of recent events to return

    Returns:
        JSON string with conversation events
    """
    try:
        # Check if task exists
        if task_id not in active_tasks:
            # Try to load from disk
            logs_dir = Path.home() / ".context-foundry" / "delegations"
            task_file = logs_dir / f"task-{task_id}.json"

            if task_file.exists():
                metadata = json.loads(task_file.read_text())
                jsonl_path = metadata.get("conversation_jsonl")
                if jsonl_path and Path(jsonl_path).exists():
                    # Load conversation from file
                    if ConversationLogger:
                        logger_instance = ConversationLogger.load_from_file(
                            Path(jsonl_path)
                        )
                        events = logger_instance.get_events(
                            event_type=event_type, last_n=last_n
                        )
                        return json.dumps(
                            {
                                "status": "success",
                                "task_id": task_id,
                                "source": "disk",
                                "event_count": len(events),
                                "events": [e.to_dict() for e in events],
                                "conversation_text": logger_instance.get_conversation_text()[
                                    -2000:
                                ],
                            },
                            indent=2,
                        )

            return json.dumps(
                {
                    "status": "error",
                    "error": f"Task ID '{task_id}' not found or no conversation logs available",
                },
                indent=2,
            )

        task_info = active_tasks[task_id]
        conversation_logger = task_info.get("conversation_logger")

        if not conversation_logger:
            return json.dumps(
                {
                    "status": "error",
                    "error": "Task is not using streaming mode - no conversation events available",
                    "hint": "Use delegate_to_claude_code_streaming() for conversation visibility",
                },
                indent=2,
            )

        events = conversation_logger.get_events(event_type=event_type, last_n=last_n)

        return json.dumps(
            {
                "status": "success",
                "task_id": task_id,
                "source": "memory",
                "is_running": task_info["process"].poll() is None,
                "event_count": len(events),
                "events": [e.to_dict() for e in events],
                "conversation_text": "\n".join(e.to_log_line() for e in events),
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
            },
            indent=2,
        )


def get_delegation_result_impl(
    task_id: str,
    include_full_output: bool,
    active_tasks: Dict[str, Dict[str, Any]],  # Reference to global active_tasks
    read_phase_info_func,  # Function reference from mcp_server
    create_output_summary_func,  # Function reference from mcp_server
    merge_project_patterns_func,  # Function reference to merge_project_patterns wrapper
) -> str:
    """
    Implementation of get_delegation_result tool.

    Gets the status and results of an async delegation task.

    Args:
        task_id: The task ID returned from delegate_to_claude_code_async()
        include_full_output: If False, return smart summary (first 50 + last 50 lines)
        active_tasks: Reference to active_tasks dict from mcp_server
        read_phase_info_func: Reference to _read_phase_info function
        create_output_summary_func: Reference to _create_output_summary function
        merge_project_patterns_func: Reference to merge_project_patterns wrapper

    Returns:
        JSON string with task status and results
    """
    try:
        # Check if task exists
        if task_id not in active_tasks:
            return json.dumps(
                {
                    "task_id": task_id,
                    "status": "not_found",
                    "error": f"Task ID '{task_id}' not found. Use list_delegations() to see active tasks.",
                },
                indent=2,
            )

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

                # Update delegation metadata on disk
                _write_delegation_metadata(
                    task_id,
                    {
                        "task_id": task_id,
                        "status": "timeout",
                        "task": task_info["task"],
                        "working_directory": task_info["cwd"],
                        "start_time": task_info["start_time"].isoformat(),
                        "end_time": datetime.now().isoformat(),
                        "duration": round(elapsed, 2),
                        "exit_code": -1,  # -1 indicates timeout/killed
                        "timeout_minutes": task_info["timeout_minutes"],
                    },
                )

                timeout_result = {
                    "task_id": task_id,
                    "status": "timeout",
                    "elapsed_seconds": elapsed,
                    "timeout_minutes": task_info["timeout_minutes"],
                    "message": f"Task exceeded timeout of {task_info['timeout_minutes']} minutes and was terminated.",
                }

                return json.dumps(timeout_result, indent=2)

            # Still running within timeout
            # Try to read phase information (with staleness check)
            phase_info = read_phase_info_func(task_info["cwd"], task_info["start_time"])

            result = {
                "task_id": task_id,
                "status": "running",
                "elapsed_seconds": round(elapsed, 2),
                "timeout_minutes": task_info["timeout_minutes"],
                "progress": f"{round((elapsed / timeout_seconds) * 100, 1)}% of timeout elapsed",
            }

            # Add phase information if available
            if phase_info:
                result["current_phase"] = phase_info.get("current_phase", "Unknown")
                result["phase_number"] = phase_info.get("phase_number", "?/7")
                result["phase_status"] = phase_info.get("status", "unknown")
                result["progress_detail"] = phase_info.get(
                    "progress_detail", "Working..."
                )
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

            # Write full output to file for later review
            output_file_path = _write_full_output_to_file(
                working_directory=task_info["cwd"],
                stdout=stdout,
                stderr=stderr,
                task_id=task_id,
            )
            task_info["output_file"] = output_file_path

            # Update delegation metadata on disk with completion info
            # Try to get phase information for enhanced metadata
            phase_info = read_phase_info_func(task_info["cwd"], task_info["start_time"])

            updated_metadata = {
                "task_id": task_id,
                "status": task_info["status"],
                "task": task_info["task"],
                "working_directory": task_info["cwd"],
                "start_time": task_info["start_time"].isoformat(),
                "end_time": datetime.now().isoformat(),
                "duration": round(elapsed, 2),
                "exit_code": process.returncode,
                "timeout_minutes": task_info["timeout_minutes"],
                "output_file": output_file_path,
                "sandbox_path": task_info.get("sandbox_path"),  # For sandbox cleanup
                "sandbox_task_id": task_info.get(
                    "sandbox_task_id"
                ),  # For sandbox cleanup
            }

            # Add phase information if available
            if phase_info:
                updated_metadata["current_phase"] = phase_info.get(
                    "current_phase", "Unknown"
                )
                updated_metadata["phase_status"] = phase_info.get("status", "unknown")
                updated_metadata["completion_percentage"] = phase_info.get(
                    "completion_percentage", 0
                )
                updated_metadata["test_iteration"] = phase_info.get("test_iteration", 0)

            _write_delegation_metadata(task_id, updated_metadata)

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
                    feedback_dir = (
                        Path(task_info["cwd"]) / ".context-foundry" / "feedback"
                    )
                    if feedback_dir.exists():
                        # Find the most recent build-feedback file
                        feedback_files = list(
                            feedback_dir.glob("build-feedback-*.json")
                        )
                        if feedback_files:
                            # Sort by modification time, get most recent
                            latest_feedback = max(
                                feedback_files, key=lambda p: p.stat().st_mtime
                            )

                            # Call merge_project_patterns to save learnings to global database
                            merge_result_str = merge_project_patterns_func(
                                project_pattern_file=str(latest_feedback),
                                pattern_type="common-issues",
                                increment_build_count=True,
                            )

                            # Parse result to check success
                            merge_result = json.loads(merge_result_str)
                            if merge_result.get("status") == "success":
                                stats = merge_result.get("merge_stats", {})
                                print("\n✅ Patterns merged to global database:")
                                print(
                                    f"   New patterns: {stats.get('new_patterns', 0)}"
                                )
                                print(
                                    f"   Updated patterns: {stats.get('updated_patterns', 0)}"
                                )
                                print(
                                    f"   Global pattern file: {merge_result.get('global_file', 'unknown')}"
                                )

                                # Store merge result in task info for reporting
                                task_info["pattern_merge_result"] = merge_result
                            else:
                                print(
                                    f"\n⚠️  Pattern merge failed: {merge_result.get('error', 'unknown error')}"
                                )
                                task_info["pattern_merge_error"] = merge_result.get(
                                    "error"
                                )

                except Exception as e:
                    # Pattern merge failure should not break the build result
                    # Just log the error and continue
                    print(f"\n⚠️  Pattern merge exception (non-critical): {e}")
                    task_info["pattern_merge_error"] = str(e)

        # Format result with smart summary (default) or full output
        if include_full_output:
            # Return full output regardless of size (may exceed token limits)
            stdout_display = task_info["stdout"] or "(empty)"
            stderr_display = task_info["stderr"] or "(empty)"
            result = {
                "task_id": task_id,
                "status": task_info["status"],
                "task": task_info["task"][:500] + "..."
                if len(task_info["task"]) > 500
                else task_info["task"],
                "working_directory": task_info["cwd"],
                "duration_seconds": round(task_info["duration"], 2),
                "exit_code": task_info["exit_code"],
                "command": " ".join(task_info["cmd"])[:200] + "..."
                if len(" ".join(task_info["cmd"])) > 200
                else " ".join(task_info["cmd"]),
                "stdout": stdout_display,
                "stderr": stderr_display,
                "output_mode": "full",
                "output_file": task_info.get("output_file", "not_created"),
            }
        else:
            # Use smart summary (first 50 + last 50 lines) to stay well under token limits
            stdout_summary, stdout_stats = create_output_summary_func(
                task_info["stdout"] or "", max_lines=50
            )
            stderr_summary, stderr_stats = create_output_summary_func(
                task_info["stderr"] or "", max_lines=50
            )

            result = {
                "task_id": task_id,
                "status": task_info["status"],
                "task": task_info["task"][:500] + "..."
                if len(task_info["task"]) > 500
                else task_info["task"],
                "working_directory": task_info["cwd"],
                "duration_seconds": round(task_info["duration"], 2),
                "exit_code": task_info["exit_code"],
                "command": " ".join(task_info["cmd"])[:200] + "..."
                if len(" ".join(task_info["cmd"])) > 200
                else " ".join(task_info["cmd"]),
                "stdout_summary": stdout_summary,
                "stderr_summary": stderr_summary,
                "output_mode": "summary",
                "output_file": task_info.get("output_file", "not_created"),
                "output_summary_info": {
                    "stdout": stdout_stats,
                    "stderr": stderr_stats,
                    "message": f"Showing first 50 + last 50 lines. Full output saved to: {task_info.get('output_file', 'not_created')}",
                },
            }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps(
            {
                "task_id": task_id,
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
            },
            indent=2,
        )


def list_delegations_impl(
    active_tasks: Dict[str, Dict[str, Any]],  # Reference to global active_tasks
) -> str:
    """
    Implementation of list_delegations tool.

    Lists all async delegation tasks (both running and completed).
    Queries THREE sources:
    1. In-memory active_tasks (current MCP server process)
    2. Daemon's SQLite database (~/.context-foundry/cfd/jobs.db) - PRIORITY
    3. Legacy delegation files (~/.context-foundry/delegations/)

    Args:
        active_tasks: Reference to active_tasks dict from mcp_server

    Returns:
        JSON string with list of all tasks and their status
    """
    try:
        import sqlite3

        tasks_list = []
        seen_task_ids = set()

        # =====================================================================
        # PRIORITY 1: Query daemon's SQLite database (most authoritative)
        # =====================================================================
        daemon_db_path = Path.home() / ".context-foundry" / "cfd" / "jobs.db"
        if daemon_db_path.exists():
            try:
                conn = sqlite3.connect(str(daemon_db_path), timeout=5.0)
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT id, type, status, priority, params_json,
                           created_at, started_at, completed_at
                    FROM jobs
                    ORDER BY created_at DESC
                    LIMIT 100
                    """
                )

                for row in cursor.fetchall():
                    task_id = row["id"]

                    # Parse params to get task description and working_directory
                    task_desc = ""
                    working_dir = ""
                    timeout_mins = 0
                    try:
                        params = (
                            json.loads(row["params_json"]) if row["params_json"] else {}
                        )
                        task_desc = params.get("task", "")[:80]
                        working_dir = params.get("working_directory", "")
                        timeout_mins = params.get("timeout_minutes", 0)
                    except Exception:
                        task_desc = "(no description)"

                    # Calculate elapsed time
                    elapsed = 0
                    if row["created_at"]:
                        try:
                            # Handle ISO format timestamps
                            created_str = row["created_at"]
                            if "T" in created_str:
                                created_time = datetime.fromisoformat(
                                    created_str.replace("Z", "+00:00")
                                )
                            else:
                                created_time = datetime.strptime(
                                    created_str, "%Y-%m-%d %H:%M:%S"
                                )
                            elapsed = (
                                datetime.now() - created_time.replace(tzinfo=None)
                            ).total_seconds()
                        except Exception:
                            pass

                    tasks_list.append(
                        {
                            "task_id": task_id,
                            "status": row["status"],
                            "task": task_desc if task_desc else f"[{row['type']}]",
                            "elapsed_seconds": round(elapsed, 2),
                            "timeout_minutes": timeout_mins,
                            "working_directory": working_dir,
                            "source": "daemon",
                            "priority": row["priority"],
                        }
                    )
                    seen_task_ids.add(task_id)

                conn.close()
            except Exception as db_error:
                # Log but don't fail - continue to other sources
                print(
                    f"Warning: Could not query daemon database: {db_error}",
                    file=sys.stderr,
                )

        # =====================================================================
        # PRIORITY 2: Add tasks from in-memory (current MCP server process)
        # =====================================================================
        for task_id, task_info in active_tasks.items():
            # Skip if already seen from daemon db
            if task_id in seen_task_ids:
                continue

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

            tasks_list.append(
                {
                    "task_id": task_id,
                    "status": status,
                    "task": task_info["task"][:80] + "..."
                    if len(task_info["task"]) > 80
                    else task_info["task"],
                    "elapsed_seconds": round(elapsed, 2),
                    "timeout_minutes": task_info["timeout_minutes"],
                    "working_directory": task_info["cwd"],
                    "source": "memory",
                }
            )
            seen_task_ids.add(task_id)

        # =====================================================================
        # PRIORITY 3: Legacy delegation files (backwards compatibility)
        # =====================================================================
        delegations_dir = Path.home() / ".context-foundry" / "delegations"
        if delegations_dir.exists():
            for task_file in delegations_dir.glob("task-*.json"):
                try:
                    metadata = json.loads(task_file.read_text())
                    task_id = metadata.get("task_id")

                    # Skip if already in list
                    if task_id in seen_task_ids:
                        continue

                    # Calculate elapsed time
                    start_time_str = metadata.get("start_time", "")
                    elapsed = 0
                    if start_time_str:
                        try:
                            start_time = datetime.fromisoformat(start_time_str)
                            elapsed = (datetime.now() - start_time).total_seconds()
                        except Exception:
                            pass

                    tasks_list.append(
                        {
                            "task_id": task_id,
                            "status": metadata.get("status", "unknown"),
                            "task": metadata.get("task", "")[:80],
                            "elapsed_seconds": round(elapsed, 2),
                            "timeout_minutes": metadata.get("timeout_minutes", 0),
                            "working_directory": metadata.get("working_directory", ""),
                            "source": "legacy",
                        }
                    )
                    seen_task_ids.add(task_id)

                except Exception:
                    continue

        if not tasks_list:
            return json.dumps(
                {"message": "No delegation tasks found", "delegations": []}, indent=2
            )

        # Sort by elapsed time (most recent first) for better UX
        tasks_list.sort(key=lambda x: x.get("elapsed_seconds", 0))

        return json.dumps(
            {
                "total_tasks": len(tasks_list),
                "delegations": tasks_list,
                "message": "Use get_delegation_result(task_id) to retrieve results. Daemon jobs shown first.",
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {"error": str(e), "traceback": traceback.format_exc()}, indent=2
        )


def cancel_delegation_impl(
    task_id: str,
    reason: Optional[str],
    active_tasks: Dict[str, Dict[str, Any]],  # Reference to global active_tasks
) -> str:
    """
    Implementation of cancel_delegation tool.

    Manually cancel/kill a running delegation task.

    Args:
        task_id: The task ID to cancel
        reason: Optional reason for cancellation (for logging/debugging)
        active_tasks: Reference to active_tasks dict from mcp_server

    Returns:
        JSON string with cancellation status and details
    """
    try:
        # Check if task exists in active_tasks (same process)
        if task_id in active_tasks:
            # Task is in memory - use existing logic
            task_info = active_tasks[task_id]
            process = task_info["process"]
        else:
            # Task not in memory - check disk for metadata and try to find process
            delegations_dir = Path.home() / ".context-foundry" / "delegations"
            task_file = delegations_dir / f"task-{task_id}.json"

            if not task_file.exists():
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"Task ID '{task_id}' not found",
                        "message": "Task metadata file does not exist",
                        "cancelled": False,
                    },
                    indent=2,
                )

            # Read metadata from disk
            try:
                metadata = json.loads(task_file.read_text())
            except Exception as e:
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"Failed to read task metadata: {str(e)}",
                        "cancelled": False,
                    },
                    indent=2,
                )

            # Get PID from metadata
            pid = metadata.get("pid")
            if not pid:
                return json.dumps(
                    {
                        "status": "error",
                        "error": "Task metadata does not contain PID",
                        "message": "Cannot cancel task without process ID",
                        "cancelled": False,
                    },
                    indent=2,
                )

            # Check if process is still running using psutil
            try:
                proc = psutil.Process(pid)

                # Verify it's actually a claude-code process (basic sanity check)
                cmdline = " ".join(proc.cmdline())
                if "claude" not in cmdline.lower() and "python" not in cmdline.lower():
                    return json.dumps(
                        {
                            "status": "error",
                            "error": f"PID {pid} exists but doesn't appear to be a claude-code process",
                            "message": f"Process command: {cmdline[:100]}",
                            "cancelled": False,
                        },
                        indent=2,
                    )

                # Kill the process
                start_time = datetime.fromisoformat(
                    metadata.get("start_time", datetime.now().isoformat())
                )
                elapsed = (datetime.now() - start_time).total_seconds()

                try:
                    # Try graceful termination first
                    proc.terminate()
                    proc.wait(timeout=5)
                    termination_method = "graceful (SIGTERM)"
                except psutil.TimeoutExpired:
                    # Force kill if graceful failed
                    proc.kill()
                    proc.wait()
                    termination_method = "forced (SIGKILL)"

                # Update metadata file
                metadata["status"] = "cancelled"
                metadata["cancelled_at"] = datetime.now().isoformat()
                metadata["cancellation_reason"] = (
                    reason or "Manual cancellation by user"
                )
                metadata["duration_seconds"] = elapsed
                metadata["termination_method"] = termination_method
                task_file.write_text(json.dumps(metadata, indent=2))

                return json.dumps(
                    {
                        "status": "success",
                        "message": f"Task cancelled successfully via {termination_method}",
                        "task_id": task_id,
                        "cancelled": True,
                        "task_summary": metadata.get("task", "")[:100],
                        "working_directory": metadata.get("working_directory", ""),
                        "elapsed_seconds": round(elapsed, 2),
                        "termination_method": termination_method,
                        "reason": reason or "Manual cancellation by user",
                        "timestamp": datetime.now().isoformat(),
                    },
                    indent=2,
                )

            except psutil.NoSuchProcess:
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"Process with PID {pid} is not running",
                        "message": "Task may have already completed or been killed",
                        "cancelled": False,
                    },
                    indent=2,
                )
            except Exception as e:
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"Failed to kill process: {str(e)}",
                        "task_id": task_id,
                        "cancelled": False,
                    },
                    indent=2,
                )

        # Continue with existing logic for in-memory tasks
        process = task_info.get("process") if isinstance(task_info, dict) else None
        if not process:
            return json.dumps(
                {
                    "status": "error",
                    "error": "Task info corrupted - no process object",
                    "cancelled": False,
                },
                indent=2,
            )

        # Check if already completed
        poll_result = process.poll()
        if poll_result is not None:
            # Process already finished
            elapsed = (datetime.now() - task_info["start_time"]).total_seconds()
            return json.dumps(
                {
                    "status": "already_finished",
                    "message": "Task already completed - cannot cancel",
                    "task_id": task_id,
                    "exit_code": poll_result,
                    "elapsed_seconds": round(elapsed, 2),
                    "cancelled": False,
                },
                indent=2,
            )

        # Calculate elapsed time before killing
        elapsed = (datetime.now() - task_info["start_time"]).total_seconds()

        # Try graceful termination first (SIGTERM)
        try:
            process.terminate()
            # Wait up to 5 seconds for graceful shutdown
            try:
                process.wait(timeout=5)
                termination_method = "graceful (SIGTERM)"
            except subprocess.TimeoutExpired:
                # Force kill if graceful termination failed (SIGKILL)
                process.kill()
                process.wait()
                termination_method = "forced (SIGKILL)"
        except Exception:
            # If terminate/kill fails, try kill directly
            try:
                process.kill()
                process.wait()
                termination_method = "forced (SIGKILL - fallback)"
            except Exception as kill_error:
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"Failed to kill process: {str(kill_error)}",
                        "task_id": task_id,
                        "cancelled": False,
                    },
                    indent=2,
                )

        # Capture any remaining output
        try:
            stdout = process.stdout.read() if process.stdout else ""
            stderr = process.stderr.read() if process.stderr else ""
        except Exception:
            stdout = "(could not read stdout)"
            stderr = "(could not read stderr)"

        # Update task info
        task_info["status"] = "cancelled"
        task_info["cancelled_at"] = datetime.now().isoformat()
        task_info["cancellation_reason"] = reason or "Manual cancellation by user"
        task_info["duration"] = elapsed
        task_info["exit_code"] = -15  # Standard SIGTERM exit code
        task_info["stdout"] = stdout
        task_info["stderr"] = stderr
        task_info["termination_method"] = termination_method

        # Write partial output to file for debugging
        output_file_path = _write_full_output_to_file(
            working_directory=task_info["cwd"],
            stdout=stdout or "(cancelled - no output)",
            stderr=stderr or "(cancelled - no output)",
            task_id=task_id,
        )
        task_info["output_file"] = output_file_path

        # Update shared delegation metadata file so other processes see the cancellation
        try:
            delegations_dir = Path.home() / ".context-foundry" / "delegations"
            task_file = delegations_dir / f"task-{task_id}.json"
            if task_file.exists():
                metadata = json.loads(task_file.read_text())
                metadata["status"] = "cancelled"
                metadata["end_time"] = datetime.now().isoformat()
                metadata["cancelled_at"] = datetime.now().isoformat()
                metadata["cancellation_reason"] = (
                    reason or "Manual cancellation by user"
                )
                metadata["duration"] = round(elapsed, 2)
                metadata["exit_code"] = -15  # Standard SIGTERM exit code
                metadata["termination_method"] = termination_method
                metadata["output_file"] = output_file_path
                task_file.write_text(json.dumps(metadata, indent=2))
        except Exception:
            # Don't fail the cancellation if metadata update fails
            pass

        return json.dumps(
            {
                "status": "success",
                "message": f"Task cancelled successfully via {termination_method}",
                "task_id": task_id,
                "cancelled": True,
                "task_summary": task_info["task"][:100]
                + ("..." if len(task_info["task"]) > 100 else ""),
                "working_directory": task_info["cwd"],
                "elapsed_seconds": round(elapsed, 2),
                "termination_method": termination_method,
                "reason": reason or "Manual cancellation by user",
                "output_file": output_file_path,
                "timestamp": datetime.now().isoformat(),
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "task_id": task_id,
                "cancelled": False,
            },
            indent=2,
        )


def stream_delegation_output_impl(
    task_id: str,
    lines: int,
    include_phase_info: bool,
    filter_pattern: Optional[str],
    active_tasks: Dict[str, Dict[str, Any]],  # Reference to global active_tasks
    read_phase_info_func,  # Function reference from mcp_server
) -> str:
    """
    Implementation of stream_delegation_output tool.

    Stream raw, real-time output from a running or completed delegation task.

    Args:
        task_id: The task ID to stream output from
        lines: Number of recent lines to show (default: 50)
        include_phase_info: Whether to prepend current phase information
        filter_pattern: Optional regex pattern to filter lines
        active_tasks: Reference to active_tasks dict from mcp_server
        read_phase_info_func: Reference to _read_phase_info function

    Returns:
        JSON string with streaming output and metadata
    """
    try:
        # Check if task exists
        if task_id not in active_tasks:
            return json.dumps(
                {
                    "status": "error",
                    "error": f"Task ID '{task_id}' not found",
                    "message": "Use list_delegations() to see active tasks",
                    "task_id": task_id,
                },
                indent=2,
            )

        task_info = active_tasks[task_id]
        process = task_info["process"]

        # Check process status
        poll_result = process.poll()
        is_running = poll_result is None

        elapsed = (datetime.now() - task_info["start_time"]).total_seconds()

        # Read current output from process
        # For running processes, we need to read without blocking
        # For completed processes, we can read all available output
        stdout_data = ""
        stderr_data = ""

        try:
            if is_running:
                # For running process, read what's available without blocking
                # This is tricky - we can't use non-blocking reads easily
                # Instead, we'll check if we've already captured output
                if task_info.get("stdout"):
                    stdout_data = task_info["stdout"]
                if task_info.get("stderr"):
                    stderr_data = task_info["stderr"]

                # Try to read more (this might block briefly)
                # We'll use a small buffer approach
                try:
                    # Check if there's data available (Unix-only)
                    if process.stdout and hasattr(select, "select"):
                        readable, _, _ = select.select([process.stdout], [], [], 0.1)
                        if readable:
                            # Read available data
                            new_data = process.stdout.read(8192)  # Read up to 8KB
                            if new_data:
                                stdout_data += new_data
                                task_info["stdout"] = stdout_data

                    if process.stderr and hasattr(select, "select"):
                        readable, _, _ = select.select([process.stderr], [], [], 0.1)
                        if readable:
                            new_data = process.stderr.read(8192)
                            if new_data:
                                stderr_data += new_data
                                task_info["stderr"] = stderr_data
                except Exception:
                    # If select doesn't work (Windows or other issues), use stored data
                    pass
            else:
                # Process completed - read all output
                if task_info.get("stdout"):
                    stdout_data = task_info["stdout"]
                else:
                    try:
                        stdout_data = process.stdout.read() if process.stdout else ""
                        task_info["stdout"] = stdout_data
                    except Exception:
                        stdout_data = "(could not read stdout)"

                if task_info.get("stderr"):
                    stderr_data = task_info["stderr"]
                else:
                    try:
                        stderr_data = process.stderr.read() if process.stderr else ""
                        task_info["stderr"] = stderr_data
                    except Exception:
                        stderr_data = "(could not read stderr)"
        except Exception as read_error:
            stdout_data = f"(error reading output: {read_error})"
            stderr_data = ""

        # Combine stdout and stderr
        combined_output = ""
        if stdout_data:
            combined_output += f"=== STDOUT ===\n{stdout_data}\n\n"
        if stderr_data:
            combined_output += f"=== STDERR ===\n{stderr_data}\n\n"

        if not combined_output:
            combined_output = "(no output yet)\n"

        # Split into lines
        all_lines = combined_output.split("\n")

        # Apply filter if specified
        if filter_pattern:
            try:
                pattern = re.compile(filter_pattern, re.IGNORECASE)
                filtered_lines = [line for line in all_lines if pattern.search(line)]
                display_lines = filtered_lines
                filter_info = f"Filtered by pattern '{filter_pattern}': {len(filtered_lines)} / {len(all_lines)} lines matched"
            except re.error as e:
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"Invalid regex pattern: {str(e)}",
                        "task_id": task_id,
                    },
                    indent=2,
                )
        else:
            display_lines = all_lines
            filter_info = None

        # Get last N lines
        if len(display_lines) > lines:
            shown_lines = display_lines[-lines:]
            truncated = True
            hidden_lines = len(display_lines) - lines
        else:
            shown_lines = display_lines
            truncated = False
            hidden_lines = 0

        output_text = "\n".join(shown_lines)

        # Get phase information if requested
        phase_info = {}
        if include_phase_info:
            try:
                phase_data = read_phase_info_func(
                    task_info["cwd"], task_info["start_time"]
                )
                if phase_data:
                    phase_info = {
                        "current_phase": phase_data.get("current_phase", "Unknown"),
                        "phase_number": phase_data.get("phase_number", "?/7"),
                        "status": phase_data.get("status", "unknown"),
                        "progress_detail": phase_data.get("progress_detail", ""),
                        "test_iteration": phase_data.get("test_iteration", 0),
                        "phases_completed": phase_data.get("phases_completed", []),
                    }
            except Exception:
                phase_info = {"error": "Could not read phase info"}

        # Build response
        response = {
            "status": "success",
            "task_id": task_id,
            "task_summary": task_info["task"][:80]
            + ("..." if len(task_info["task"]) > 80 else ""),
            "working_directory": task_info["cwd"],
            "is_running": is_running,
            "elapsed_seconds": round(elapsed, 2),
            "output_info": {
                "total_lines": len(all_lines),
                "shown_lines": len(shown_lines),
                "hidden_lines": hidden_lines,
                "truncated": truncated,
                "filter_applied": filter_pattern is not None,
                "filter_info": filter_info,
            },
            "raw_output": output_text,
            "timestamp": datetime.now().isoformat(),
        }

        if include_phase_info and phase_info:
            response["phase_info"] = phase_info

        # Add helpful hints
        if is_running:
            response["hint"] = (
                "Task is still running. Call this tool again to see new output."
            )
        else:
            response["hint"] = (
                f"Task completed with exit code {poll_result}. Use get_delegation_result('{task_id}') for full results."
            )

        return json.dumps(response, indent=2)

    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "task_id": task_id,
            },
            indent=2,
        )
