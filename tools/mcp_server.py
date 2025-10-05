#!/usr/bin/env python3
"""
MCP Server for Context Foundry
Enables Claude Desktop to use Context Foundry without API charges
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Optional

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
    print("📋 Available tools: context_foundry_build, context_foundry_enhance, context_foundry_status", file=sys.stderr)
    print("💡 Configure in Claude Desktop to use without API charges!", file=sys.stderr)

    mcp.run()
