#!/usr/bin/env python3
"""
⚠️  DEPRECATED - MARKED FOR RETIREMENT ⚠️

This runner uses the Python orchestrator with direct API calls.
See: DEPRECATION_NOTICE.md for migration path.

REPLACEMENT: Sequential mode with /agents command (use_parallel=False)

---

Subprocess runner for parallel autonomous builds (LEGACY)
This script is spawned as a background process by the MCP server.
"""

import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env file FIRST (before any imports that might use env vars)
load_dotenv()

# Add parent directory to path for imports
FOUNDRY_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(FOUNDRY_ROOT))

from workflows.autonomous_orchestrator import AutonomousOrchestrator


def main():
    """
    Run a parallel autonomous build from JSON config passed via stdin.

    Expected JSON input:
    {
        "task": "Build description",
        "working_directory": "/path/to/project",
        "project_name": "project-name",
        "github_repo_name": "repo-name" (optional),
        "enable_test_loop": true,
        "max_test_iterations": 3
    }
    """
    try:
        # Read config from stdin
        config = json.loads(sys.stdin.read())

        task = config["task"]
        working_directory = Path(config["working_directory"])
        project_name = config.get("project_name") or working_directory.name
        github_repo_name = config.get("github_repo_name")
        enable_test_loop = config.get("enable_test_loop", True)
        max_test_iterations = config.get("max_test_iterations", 3)

        print(f"🚀 Starting parallel autonomous build...", file=sys.stderr)
        print(f"Project: {project_name}", file=sys.stderr)
        print(f"Location: {working_directory}", file=sys.stderr)
        print(f"Task: {task[:100]}...", file=sys.stderr)
        print("", file=sys.stderr)

        # Create orchestrator with parallel mode enabled
        orchestrator = AutonomousOrchestrator(
            project_name=project_name,
            task_description=task,
            project_dir=working_directory,
            autonomous=True,
            use_multi_agent=True,  # Enable parallelization
            use_patterns=True,
            enable_livestream=False,
            auto_push=True if github_repo_name else False
        )

        # Run the build (this will take 10-15 minutes)
        result = orchestrator.run()

        # Output result as JSON to stdout
        output = {
            'success': result.get('status') == 'success',
            'result': result,
            'project_dir': str(working_directory),
            'github_repo': github_repo_name,
            'multi_agent_used': True,
            'project_name': project_name
        }

        print(json.dumps(output, indent=2))

        # Exit with 0 for success, 1 for failure
        sys.exit(0 if output['success'] else 1)

    except Exception as e:
        import traceback
        error_output = {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }
        print(json.dumps(error_output, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
