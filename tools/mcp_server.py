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

from workflows.autonomous_orchestrator import AutonomousOrchestrator

# Create MCP server
mcp = FastMCP("Context Foundry")

# Track active builds
active_builds = {}

# Track async delegation tasks
# Structure: {task_id: {process, cmd, cwd, start_time, status, result, stdout, stderr, duration}}
active_tasks: Dict[str, Dict[str, Any]] = {}


@mcp.tool()
async def context_foundry_build(
    task_description: str,
    project_name: Optional[str] = None,
    autonomous: bool = False,
    use_patterns: bool = True
) -> str:
    """
    Build a new project from scratch using Context Foundry's Scout → Architect → Builder workflow.

    Args:
        task_description: Description of what to build (e.g., "Create a todo app with REST API")
        project_name: Optional name for the project (auto-generated if not provided)
        autonomous: If True, skip human review checkpoints
        use_patterns: If True, use pattern library for better results

    Returns:
        Status message with build results
    """
    try:
        # Get FastMCP context
        ctx = get_context()

        # Check if client supports sampling by attempting a test call
        # Context Foundry requires MCP sampling, which Claude Desktop doesn't yet support
        try:
            # Try a minimal sampling request to check support
            await ctx.sample("test", max_tokens=1)
        except ValueError as e:
            if "does not support sampling" in str(e):
                return f"""❌ MCP Sampling Not Supported

Context Foundry requires MCP sampling to function, but Claude Desktop doesn't yet support this feature.

**Why this is needed:**
Context Foundry uses a Scout → Architect → Builder workflow that requires multiple LLM calls to:
- Research and design architecture (Scout)
- Create specifications and plans (Architect)
- Generate working code (Builder)

**Alternative - Use API Mode:**
You can use Context Foundry's CLI with an Anthropic API key:

1. Get an API key from https://console.anthropic.com/
2. Set environment variable:
   ```bash
   export ANTHROPIC_API_KEY=your_key_here
   ```

3. Run the build:
   ```bash
   foundry build {project_name or 'my-app'} "{task_description}"
   ```

**Example:**
```bash
foundry build hello-foundry "Create a simple Python script with one file (hello.py) that prints 'Hello from Context Foundry!'"
```

**Cost:** API mode: ~$3-10 per project in API charges. MCP mode (when available): No per-token charges, uses your Claude subscription.

**Status:** MCP mode will be enabled automatically when Claude Desktop adds sampling support.
Documentation: https://modelcontextprotocol.io/docs/concepts/sampling
"""
            else:
                raise  # Different error, re-raise it

        # If we get here, sampling IS supported! Proceed with build
        # Auto-generate project name if not provided
        if not project_name:
            project_name = task_description.lower().replace(" ", "-")[:30]

        # Change to context-foundry base directory so relative paths work
        base_dir = Path(__file__).parent.parent
        original_cwd = os.getcwd()
        os.chdir(base_dir)

        # Use absolute path for project directory
        project_dir = base_dir / "examples" / project_name

        # Create orchestrator with MCP context
        orchestrator = AutonomousOrchestrator(
            task_description=task_description,
            project_name=project_name,
            mode="new",
            autonomous=autonomous,
            use_patterns=use_patterns,
            project_dir=project_dir,
            ctx=ctx
        )

        # Run the workflow
        try:
            result = orchestrator.run()

            if result["success"]:
                return f"""✅ Build Complete!

Project: {project_name}
Location: {result.get('project_dir', 'N/A')}
Tasks Completed: {result.get('tasks_completed', 0)}

Files created:
{chr(10).join('- ' + f for f in result.get('files_created', []))}

You can now review the code and run the project!
"""
            else:
                return f"""❌ Build Failed

Error: {result.get('error', 'Unknown error')}

Check the logs for more details.
"""
        finally:
            # Restore original working directory
            os.chdir(original_cwd)

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ ERROR: {error_details}", file=sys.stderr)
        return f"❌ Error during build: {str(e)}"


@mcp.tool()
def context_foundry_enhance(
    task_description: str,
    autonomous: bool = False,
    use_patterns: bool = True
) -> str:
    """
    Enhance an existing project with new features (Coming Soon).

    Args:
        task_description: Description of what to add/modify
        autonomous: If True, skip human review checkpoints
        use_patterns: If True, use pattern library

    Returns:
        Status message
    """
    return """🚧 Feature Coming Soon!

The 'enhance' mode is planned for Q1 2025.

Current status: You can use 'context_foundry_build' to create new projects from scratch.

For now, to modify existing code:
1. Describe the full project including existing + new features
2. Use context_foundry_build
3. Manually merge the generated code
"""


@mcp.tool()
def context_foundry_status() -> str:
    """
    Get the current status of Context Foundry.

    Returns:
        Status information including version and capabilities
    """
    return """Context Foundry MCP Server - Status

✅ Server: Running
❌ Sampling: Not supported by Claude Desktop (required for Context Foundry)

**Current Limitation:**
Context Foundry requires MCP sampling to function, but Claude Desktop doesn't yet support this feature.

**Workaround - Use API Mode:**
```bash
export ANTHROPIC_API_KEY=your_key_here
foundry build my-app "description of what to build"
```

**Available Tools:**
- context_foundry_build: Returns error message about sampling (not functional yet)
- context_foundry_enhance: Coming soon
- context_foundry_status: This status message

**When will MCP mode work?**
Automatically when Claude Desktop adds sampling support. No code changes needed.
Benefits: No per-token API charges, uses your Claude Pro/Max subscription instead.

**More info:** https://modelcontextprotocol.io/docs/concepts/sampling
"""


@mcp.tool()
def delegate_to_claude_code(
    task: str,
    working_directory: Optional[str] = None,
    timeout_minutes: float = 10.0,
    additional_flags: Optional[str] = None
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

    Returns:
        Formatted output with status, duration, stdout, and stderr

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
        cmd = ["claude", "--print", "--permission-mode", "bypassPermissions", "--strict-mcp-config"]

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

        output = f"""{status_emoji} Claude Code Delegation {status_text}

**Task:** {task}
**Working Directory:** {cwd}
**Duration:** {duration_formatted}
**Command:** {' '.join(cmd)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 STDOUT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{result.stdout if result.stdout else "(empty)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📥 STDERR:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{result.stderr if result.stderr else "(empty)"}
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
        # Build the command
        cmd = ["claude", "--print", "--permission-mode", "bypassPermissions", "--strict-mcp-config"]

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
def get_delegation_result(task_id: str) -> str:
    """
    Get the status and results of an async delegation task.

    Args:
        task_id: The task ID returned from delegate_to_claude_code_async()

    Returns:
        JSON string with task status and results (if complete)

    Examples:
        # Check task status
        result = get_delegation_result("abc-123-def-456")

        # If complete, result contains stdout/stderr
        # If still running, shows elapsed time
        # If failed, shows error details
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

                return json.dumps({
                    "task_id": task_id,
                    "status": "timeout",
                    "task": task_info["task"],
                    "elapsed_seconds": elapsed,
                    "timeout_minutes": task_info["timeout_minutes"],
                    "message": f"Task exceeded timeout of {task_info['timeout_minutes']} minutes and was terminated."
                }, indent=2)

            # Still running within timeout
            return json.dumps({
                "task_id": task_id,
                "status": "running",
                "task": task_info["task"],
                "elapsed_seconds": round(elapsed, 2),
                "timeout_minutes": task_info["timeout_minutes"],
                "progress": f"{round((elapsed / timeout_seconds) * 100, 1)}% of timeout elapsed"
            }, indent=2)

        # Process completed - capture output if not already captured
        if task_info["result"] is None:
            stdout, stderr = process.communicate()
            elapsed = (datetime.now() - task_info["start_time"]).total_seconds()

            task_info["stdout"] = stdout
            task_info["stderr"] = stderr
            task_info["duration"] = elapsed
            task_info["exit_code"] = process.returncode
            task_info["status"] = "completed" if process.returncode == 0 else "failed"

        # Format result
        result = {
            "task_id": task_id,
            "status": task_info["status"],
            "task": task_info["task"],
            "working_directory": task_info["cwd"],
            "duration_seconds": round(task_info["duration"], 2),
            "exit_code": task_info["exit_code"],
            "command": " ".join(task_info["cmd"]),
            "stdout": task_info["stdout"] or "(empty)",
            "stderr": task_info["stderr"] or "(empty)",
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
    timeout_minutes: float = 90.0
) -> str:
    """
    Fully autonomous build/test/fix/deploy with self-healing test loop.

    Spawns fresh Claude instance that:
    - Creates Scout/Architect/Builder/Tester agents via /agents
    - Implements complete project
    - Tests automatically
    - If tests fail: Goes back to Architect → Builder → Test (up to max_test_iterations)
    - If tests pass: Deploys to GitHub
    - Zero human intervention

    Args:
        task: What to build/fix/enhance
        working_directory: Where to work
        github_repo_name: Create new repo (optional)
        existing_repo: Fix/enhance existing (optional)
        mode: "new_project", "fix_bugs", "add_docs"
        enable_test_loop: Enable self-healing test loop (default: True)
        max_test_iterations: Max test/fix cycles (default: 3)
        timeout_minutes: Max execution time (default: 90)

    Returns:
        JSON with completion status, GitHub URL, test results

    Examples:
        # Build new project with testing
        autonomous_build_and_deploy(
            task="Build MVP Mario Bros HTML5 game with jump, run, coins",
            working_directory="/Users/name/homelab/mario-game",
            github_repo_name="mario-game-mvp",
            enable_test_loop=True,
            max_test_iterations=3
        )

        # Fix bugs without test loop (faster)
        autonomous_build_and_deploy(
            task="Fix TypeScript errors",
            working_directory="/Users/name/homelab/my-app",
            existing_repo="snedea/my-app",
            mode="fix_bugs",
            enable_test_loop=False
        )
    """
    try:
        # Create orchestrator task configuration
        task_config = {
            "task": task,
            "working_directory": working_directory,
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

        # Build command
        cmd = [
            "claude", "--print",
            "--permission-mode", "bypassPermissions",
            "--strict-mcp-config",
            "--system-prompt", system_prompt,
            task_prompt
        ]

        # Validate/create working directory
        working_dir_path = Path(working_directory)
        if not working_dir_path.exists():
            working_dir_path.mkdir(parents=True, exist_ok=True)

        # Execute (blocking - this is intentionally synchronous for autonomous work)
        start_time = time.time()

        result = subprocess.run(
            cmd,
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=timeout_minutes * 60,
            stdin=subprocess.DEVNULL,
            env={
                **os.environ,
                'PYTHONUNBUFFERED': '1',
            }
        )

        duration = time.time() - start_time

        # Parse result
        try:
            # Try to extract JSON from output
            # The orchestrator should return pure JSON
            output_json = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            # If not valid JSON, wrap the output
            output_json = {
                "status": "completed" if result.returncode == 0 else "failed",
                "raw_output": result.stdout,
                "raw_error": result.stderr,
                "note": "Delegated instance did not return valid JSON"
            }

        # Add execution metadata
        output_json["execution_duration_minutes"] = round(duration / 60, 2)
        output_json["exit_code"] = result.returncode
        output_json["task_config"] = task_config

        return json.dumps(output_json, indent=2)

    except subprocess.TimeoutExpired:
        return json.dumps({
            "status": "timeout",
            "message": f"Task exceeded {timeout_minutes} minute timeout",
            "task": task,
            "working_directory": working_directory
        }, indent=2)

    except FileNotFoundError:
        return json.dumps({
            "status": "error",
            "error": "claude command not found",
            "message": "Make sure Claude CLI is installed and in PATH",
            "path": os.environ.get('PATH', 'not set')
        }, indent=2)

    except Exception as e:
        import traceback
        return json.dumps({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "task": task,
            "working_directory": working_directory
        }, indent=2)


@mcp.tool()
def autonomous_build_and_deploy_async(
    task: str,
    working_directory: str,
    github_repo_name: Optional[str] = None,
    existing_repo: Optional[str] = None,
    mode: str = "new_project",
    enable_test_loop: bool = True,
    max_test_iterations: int = 3,
    timeout_minutes: float = 90.0
) -> str:
    """
    Fully autonomous build/test/fix/deploy (ASYNC - runs in background).

    Same as autonomous_build_and_deploy() but NON-BLOCKING:
    - Starts the build immediately
    - Returns task_id right away
    - Build runs in background while you continue working
    - Use get_delegation_result(task_id) to check status
    - Use list_delegations() to see all running builds

    Perfect for "walk away" builds - you can work on other things while it builds.

    Args:
        task: What to build/fix/enhance
        working_directory: Where to work
        github_repo_name: Create new repo (optional)
        existing_repo: Fix/enhance existing (optional)
        mode: "new_project", "fix_bugs", "add_docs"
        enable_test_loop: Enable self-healing test loop (default: True)
        max_test_iterations: Max test/fix cycles (default: 3)
        timeout_minutes: Max execution time (default: 90)

    Returns:
        JSON with task_id and status (immediately)

    Examples:
        # Start build in background
        result = autonomous_build_and_deploy_async(
            task="Build weather app with OpenWeatherMap API",
            working_directory="/tmp/weather-app",
            github_repo_name="weather-app",
            enable_test_loop=True
        )
        # Returns: {"task_id": "abc-123", "status": "started", ...}

        # Continue working...

        # Check status later
        status = get_delegation_result("abc-123")

        # List all builds
        all_builds = list_delegations()
    """
    try:
        # Create orchestrator task configuration
        task_config = {
            "task": task,
            "working_directory": working_directory,
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

        # Build command
        cmd = [
            "claude", "--print",
            "--permission-mode", "bypassPermissions",
            "--strict-mcp-config",
            "--system-prompt", system_prompt,
            task_prompt
        ]

        # Validate/create working directory
        working_dir_path = Path(working_directory)
        if not working_dir_path.exists():
            working_dir_path.mkdir(parents=True, exist_ok=True)

        # Generate unique task ID
        task_id = str(uuid.uuid4())

        # Start the process (NON-BLOCKING)
        process = subprocess.Popen(
            cmd,
            cwd=working_directory,
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
            "cwd": working_directory,
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

        # Extract project name for display
        project_name = github_repo_name or Path(working_directory).name

        return json.dumps({
            "task_id": task_id,
            "status": "started",
            "project": project_name,
            "task_summary": task[:100] + ("..." if len(task) > 100 else ""),
            "working_directory": working_directory,
            "github_repo": github_repo_name,
            "timeout_minutes": timeout_minutes,
            "enable_test_loop": enable_test_loop,
            "message": f"""
🚀 Autonomous build started!

Project: {project_name}
Task ID: {task_id}
Location: {working_directory}
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
        return json.dumps({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "task": task,
            "working_directory": working_directory
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
    print("🚀 Starting Context Foundry MCP Server...", file=sys.stderr)
    print("📋 Available tools:", file=sys.stderr)
    print("   - context_foundry_build: Build projects using Context Foundry", file=sys.stderr)
    print("   - context_foundry_enhance: Enhance existing projects (coming soon)", file=sys.stderr)
    print("   - context_foundry_status: Get server status", file=sys.stderr)
    print("   - delegate_to_claude_code: Delegate tasks to fresh Claude instances (synchronous)", file=sys.stderr)
    print("   - delegate_to_claude_code_async: Delegate tasks asynchronously (parallel execution)", file=sys.stderr)
    print("   - get_delegation_result: Check status and get results of async tasks", file=sys.stderr)
    print("   - list_delegations: List all active and completed async tasks", file=sys.stderr)
    print("   - autonomous_build_and_deploy: Fully autonomous Scout→Architect→Builder→Test→Deploy with self-healing", file=sys.stderr)
    print("💡 Configure in Claude Desktop or Claude Code CLI to use this server!", file=sys.stderr)

    mcp.run()
