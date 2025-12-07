"""
MCP-to-Daemon Integration Utilities

This module provides utilities for integrating MCP server tools with the
Context Foundry Daemon. Instead of spawning subprocess directly, MCP tools
submit jobs to the daemon queue for proper orchestration.

Benefits:
- Job persistence (survives MCP disconnections)
- Working directory locking (prevents conflicts)
- Progress monitoring via CLI (cfd logs <job-id> --follow)
- Automatic retry on failures
- Pattern merging guaranteed
- Centralized job tracking in SQLite database
"""

import json
import sys
from pathlib import Path
from typing import Optional, List

from context_foundry.daemon.config import Config
from context_foundry.daemon.jobs import JobManager
from context_foundry.daemon.models import JobType
from context_foundry.daemon.server import get_running_daemon_pid
from context_foundry.daemon.store import Store


def ensure_daemon_running() -> tuple[bool, Optional[str]]:
    """
    Check if CF Daemon is running and return status.

    Returns:
        (is_running, error_message)
        - is_running: True if daemon is running
        - error_message: None if running, helpful error message otherwise
    """
    config = Config.load()
    pid = get_running_daemon_pid(config)

    if not pid:
        error_msg = """
❌ Context Foundry Daemon is not running

The daemon is required for autonomous builds through MCP.

Start the daemon:
  cfd start

Check status:
  cfd status

Monitor builds in real-time:
  cfd logs <job-id> --follow

After starting the daemon, try your build again.
""".strip()
        return False, error_msg

    print(f"✅ CF Daemon is running (PID: {pid})", file=sys.stderr)
    return True, None


def submit_autonomous_build_to_daemon(
    task: str,
    working_directory: str,
    github_repo_name: Optional[str] = None,
    mode: str = "new_project",
    max_test_iterations: int = 3,
    timeout_minutes: float = 90.0,
    use_parallel: bool = False,
    incremental: bool = False,
    force_rebuild: bool = False,
    pause_after_phases: Optional[List[str]] = None,
    execution_mode: str = "autonomous",
) -> str:
    """
    Submit autonomous build job to CF Daemon queue.

    This replaces direct subprocess spawning with daemon-based job submission,
    providing better reliability, monitoring, and concurrency control.

    Args:
        task: Build task description
        working_directory: Where to create the project
        github_repo_name: Optional GitHub repo name
        mode: Build mode (new_project, enhancement, etc.)
        max_test_iterations: Maximum test/fix iterations
        timeout_minutes: Job timeout in minutes
        use_parallel: Enable parallel builders
        incremental: Enable incremental builds
        force_rebuild: Force full rebuild
        pause_after_phases: Phases to pause after (e.g., ["Scout", "Architect"])
        execution_mode: "autonomous", "interactive", or "selective"

    Returns:
        JSON string with job submission result
    """
    # Ensure daemon is running
    is_running, error_msg = ensure_daemon_running()
    if not is_running:
        return json.dumps({"status": "error", "error": error_msg}, indent=2)

    # Load daemon configuration
    config = Config.load()
    store = Store(config.db_path)

    # Create JobManager (no runner needed for submission)
    job_manager = JobManager(config, store, runner=None)

    # =========================================================================
    # CRITICAL: Resolve working directory to ABSOLUTE path before submitting
    # to daemon. The daemon runs with chdir("/") after double-fork, so any
    # relative paths would resolve incorrectly to the filesystem root.
    #
    # Smart defaults:
    # - Relative paths (e.g., "weather-app") → sibling to context-foundry
    #   Example: ~/projects/weather-app
    # - Absolute paths (e.g., "/tmp/test") → used as-is (explicit override)
    # =========================================================================
    from tools.mcp_utils.path_utils import get_projects_root

    working_dir_input = Path(working_directory)
    if working_dir_input.is_absolute():
        final_working_dir = working_dir_input
        print(
            f"📍 Using explicit working directory: {working_dir_input}",
            file=sys.stderr,
        )
    else:
        projects_root = get_projects_root()
        final_working_dir = projects_root / working_directory
        print(
            f"📍 Creating project in: {final_working_dir} (sibling to context-foundry)",
            file=sys.stderr,
        )

    # Convert to absolute path string for daemon
    final_working_dir_str = str(final_working_dir.resolve())

    # Prepare job parameters
    # These match the signature of autonomous_build_and_deploy_impl
    params = {
        "task": task,
        "working_directory": final_working_dir_str,  # Absolute path
        "github_repo_name": github_repo_name,
        "mode": mode,
        "max_test_iterations": max_test_iterations,
        "timeout_minutes": timeout_minutes,
        "use_parallel": use_parallel,
        "incremental": incremental,
        "force_rebuild": force_rebuild,
        "pause_after_phases": pause_after_phases or [],
        "execution_mode": execution_mode,
    }

    # Submit job to daemon queue
    try:
        job = job_manager.submit_job(
            job_type=JobType.AUTONOMOUS_BUILD,  # Full Scout→Architect→Builder→Test flow
            params=params,
            priority=5,  # Default priority
            max_retries=3,  # Retry up to 3 times on failure
            metadata={
                "source": "mcp_server",
                "build_type": mode,  # Use actual mode (new_project, enhancement, etc.)
                "project_name": github_repo_name or final_working_dir.name,
            },
        )

        # Extract project name for display
        project_name = github_repo_name or final_working_dir.name

        # Note: The actual working directory may have a random ID appended by the runner
        # to prevent overwriting existing projects. We show the base path here, but users
        # should check job.params['working_directory'] for the final path.
        mode = params.get("mode", "new_project")
        path_note = ""
        if mode == "new_project":
            path_note = f"\nNote: A random ID will be appended to prevent overwrites (e.g., {project_name}-c4r)"

        # Return success response with monitoring instructions
        return json.dumps(
            {
                "job_id": job.id,
                "status": "queued",
                "project": project_name,
                "working_directory": final_working_dir_str,
                "timeout_minutes": timeout_minutes,
                "message": f"""
🚀 Build job submitted to CF Daemon!

Job ID: {job.id}
Project: {project_name}
Status: {job.status.value}
Priority: {job.priority}
Working Directory: {final_working_dir_str}{path_note}

The daemon will execute this build when a worker is available.

Monitor progress:
  cfd show {job.id}           # View job details (includes actual path)
  cfd logs {job.id} --follow  # Stream live logs
  cfd list                    # List all jobs

Check status anytime:
  "What's the status of job {job.id}?"
  "Show all my builds"

Expected phases:
  Scout → Architect → Builder → Test → Complete

Expected duration: 7-15 minutes
""".strip(),
            },
            indent=2,
        )

    except Exception as e:
        # Handle submission errors
        error_msg = f"Failed to submit job to daemon: {str(e)}"
        print(f"❌ {error_msg}", file=sys.stderr)

        return json.dumps(
            {
                "status": "error",
                "error": error_msg,
                "suggestion": "Check daemon logs: cfd logs --daemon",
            },
            indent=2,
        )


def get_job_status_from_daemon(job_id: str) -> str:
    """
    Get current status of a job from daemon database.

    Args:
        job_id: Job ID to query

    Returns:
        JSON string with job status
    """
    try:
        config = Config.load()
        store = Store(config.db_path)

        # Get job from database
        job = store.get_job(job_id)

        if not job:
            return json.dumps(
                {"status": "error", "error": f"Job {job_id} not found"}, indent=2
            )

        # Format response
        return json.dumps(
            {
                "job_id": job.id,
                "status": job.status.value,
                "job_type": job.type.value,  # Fixed: job.type not job.job_type
                "priority": job.priority,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": (
                    job.completed_at.isoformat() if job.completed_at else None
                ),
                "retry_count": job.retry_count,
                "max_retries": job.max_retries,
                "error": job.error,
                "result": job.result,
                "params": job.params,
                "metadata": job.metadata,
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": f"Failed to query job status: {str(e)}"},
            indent=2,
        )
