#!/usr/bin/env python3
"""
MCP Wrapper for Mission Control
Provides simple CLI access to MCP server functions without requiring direct imports in the TUI
"""

import sys
import json
import argparse
import os
from pathlib import Path

# Suppress diagnostic output to keep stdout clean for JSON
# Redirect stdout temporarily to capture only the JSON result
import io

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def call_autonomous_build(task: str, working_directory: str, github_repo_name: str, model: str = "sonnet"):
    """Call the autonomous build MCP function via async delegation"""
    try:
        # Suppress stdout during import and call to avoid diagnostic output
        original_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            # Import here so errors are caught gracefully
            from tools.mcp_server import autonomous_build_and_deploy

            # Build the full task description with all parameters
            # This will be delegated to a background claude-code process
            full_task = json.dumps({
                "task": task,
                "working_directory": working_directory,
                "github_repo_name": github_repo_name,
                "mode": "new_project",
                "model": model
            })

            # Call the MCP function directly - it uses async delegation internally
            # This returns immediately with a task ID
            # MCP-decorated functions need to be called via their fn attribute
            if hasattr(autonomous_build_and_deploy, 'fn'):
                result = autonomous_build_and_deploy.fn(
                    task=task,
                    working_directory=working_directory,
                    github_repo_name=github_repo_name,
                    mode="new_project"
                )
            else:
                result = autonomous_build_and_deploy(
                    task=task,
                    working_directory=working_directory,
                    github_repo_name=github_repo_name,
                    mode="new_project"
                )
        finally:
            # Restore stdout
            sys.stdout = original_stdout

        # Result is a JSON string with task_id, status, etc.
        print(result)
        return 0

    except ImportError as e:
        print(json.dumps({
            "error": "MCP dependencies not available",
            "message": str(e),
            "help": "This feature requires Python 3.10+ and FastMCP. Install with: pip install -r requirements-mcp.txt"
        }), file=sys.stderr)
        return 1
    except Exception as e:
        print(json.dumps({
            "error": "Build failed",
            "message": str(e),
            "type": type(e).__name__
        }), file=sys.stderr)
        return 1


def call_status():
    """Call the MCP status function"""
    try:
        from tools.mcp_server import context_foundry_status

        # MCP-decorated functions need to be called via their fn attribute
        if hasattr(context_foundry_status, 'fn'):
            result = context_foundry_status.fn()
        else:
            result = context_foundry_status()

        print(result)
        return 0

    except ImportError as e:
        print(json.dumps({
            "error": "MCP dependencies not available",
            "message": str(e),
            "help": "MCP features require Python 3.10+ and FastMCP"
        }))
        return 1
    except Exception as e:
        print(json.dumps({
            "error": "Status check failed",
            "message": str(e)
        }))
        return 1


def call_list_delegations():
    """List active and completed delegations"""
    try:
        from tools.mcp_server import list_delegations

        # MCP-decorated functions need to be called via their fn attribute
        if hasattr(list_delegations, 'fn'):
            result = list_delegations.fn()
        else:
            result = list_delegations()

        print(result)
        return 0

    except ImportError as e:
        print(json.dumps({
            "error": "MCP dependencies not available",
            "message": str(e)
        }))
        return 1
    except Exception as e:
        print(json.dumps({
            "error": "Failed to list delegations",
            "message": str(e)
        }))
        return 1


def call_get_delegation_result(task_id: str) -> int:
    """Get detailed results for a delegation task"""
    try:
        # Suppress stdout during import
        original_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            from tools.mcp_server import get_delegation_result

            if hasattr(get_delegation_result, 'fn'):
                result = get_delegation_result.fn(task_id=task_id)
            else:
                result = get_delegation_result(task_id=task_id)
        finally:
            sys.stdout = original_stdout

        print(result)
        return 0

    except ImportError as e:
        print(json.dumps({
            "error": "MCP dependencies not available",
            "message": str(e)
        }), file=sys.stderr)
        return 1
    except Exception as e:
        print(json.dumps({
            "error": "Failed to get delegation result",
            "message": str(e)
        }), file=sys.stderr)
        return 1


def call_cancel_delegation(task_id: str, reason: str = "User requested cancellation") -> int:
    """Cancel a running delegation task"""
    try:
        # Suppress stdout during import
        original_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            from tools.mcp_server import cancel_delegation

            if hasattr(cancel_delegation, 'fn'):
                result = cancel_delegation.fn(task_id=task_id, reason=reason)
            else:
                result = cancel_delegation(task_id=task_id, reason=reason)
        finally:
            sys.stdout = original_stdout

        print(result)
        return 0

    except ImportError as e:
        print(json.dumps({
            "error": "MCP dependencies not available",
            "message": str(e)
        }), file=sys.stderr)
        return 1
    except Exception as e:
        print(json.dumps({
            "error": "Failed to cancel delegation",
            "message": str(e)
        }), file=sys.stderr)
        return 1


def call_read_patterns(pattern_type: str = "common-issues") -> int:
    """Read global patterns from pattern storage"""
    try:
        # Suppress stdout during import
        original_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            from tools.mcp_server import read_global_patterns

            if hasattr(read_global_patterns, 'fn'):
                result = read_global_patterns.fn(pattern_type=pattern_type)
            else:
                result = read_global_patterns(pattern_type=pattern_type)
        finally:
            sys.stdout = original_stdout

        print(result)
        return 0

    except ImportError as e:
        print(json.dumps({
            "error": "MCP dependencies not available",
            "message": str(e)
        }), file=sys.stderr)
        return 1
    except Exception as e:
        print(json.dumps({
            "error": "Failed to read patterns",
            "message": str(e)
        }), file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(description="MCP Wrapper for Mission Control")
    subparsers = parser.add_subparsers(dest="command", help="MCP command to execute")

    # Autonomous build command
    build_parser = subparsers.add_parser("autonomous_build", help="Start an autonomous build")
    build_parser.add_argument("--task", required=True, help="Task description")
    build_parser.add_argument("--working-directory", required=True, help="Working directory path")
    build_parser.add_argument("--github-repo-name", required=True, help="GitHub repository name")
    build_parser.add_argument("--model", default="sonnet", help="Model to use (sonnet/opus/haiku)")

    # Status command
    subparsers.add_parser("status", help="Get MCP server status")

    # List delegations command
    subparsers.add_parser("list_delegations", help="List active and completed delegations")

    # Get delegation result command
    result_parser = subparsers.add_parser("get_result", help="Get detailed results for a delegation")
    result_parser.add_argument("--task-id", required=True, help="Task ID to get results for")

    # Cancel delegation command
    cancel_parser = subparsers.add_parser("cancel", help="Cancel a running delegation")
    cancel_parser.add_argument("--task-id", required=True, help="Task ID to cancel")
    cancel_parser.add_argument("--reason", default="User requested cancellation", help="Reason for cancellation")

    # Read patterns command
    patterns_parser = subparsers.add_parser("patterns", help="Read global patterns")
    patterns_parser.add_argument("--type", default="common-issues",
                                 choices=["common-issues", "scout-learnings", "build-metrics",
                                         "architecture-patterns", "test-patterns", "mcp-server-patterns"],
                                 help="Type of patterns to read")

    args = parser.parse_args()

    if args.command == "autonomous_build":
        return call_autonomous_build(
            task=args.task,
            working_directory=args.working_directory,
            github_repo_name=args.github_repo_name,
            model=args.model
        )
    elif args.command == "status":
        return call_status()
    elif args.command == "list_delegations":
        return call_list_delegations()
    elif args.command == "get_result":
        return call_get_delegation_result(task_id=args.task_id)
    elif args.command == "cancel":
        return call_cancel_delegation(task_id=args.task_id, reason=args.reason)
    elif args.command == "patterns":
        return call_read_patterns(pattern_type=args.type)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
