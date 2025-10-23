#!/usr/bin/env python3
"""
Test script for parallel build runner.
This simulates what the MCP server does when spawning a parallel build.
"""

import json
import subprocess
import sys
from pathlib import Path

def test_runner():
    """Test the parallel build runner with a simple config."""

    # Create a test config
    test_config = {
        "task": "Create a simple Hello World Python script",
        "working_directory": "/tmp/cf-test-runner",
        "project_name": "test-hello-world",
        "github_repo_name": None,
        "enable_test_loop": False,
        "max_test_iterations": 1
    }

    # Make sure test directory exists
    Path(test_config["working_directory"]).mkdir(parents=True, exist_ok=True)

    # Get path to runner script
    runner_script = Path(__file__).parent / "run_parallel_build.py"

    # Build command
    cmd = [sys.executable, str(runner_script)]

    print("🧪 Testing parallel build runner...")
    print(f"Config: {json.dumps(test_config, indent=2)}")
    print(f"Command: {' '.join(cmd)}")
    print("")

    # Run the subprocess
    try:
        process = subprocess.Popen(
            cmd,
            cwd=test_config["working_directory"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True
        )

        # Send config to stdin
        stdout, stderr = process.communicate(input=json.dumps(test_config), timeout=30)

        print("STDOUT:")
        print(stdout)
        print("\nSTDERR:")
        print(stderr)
        print(f"\nExit code: {process.returncode}")

        if process.returncode == 0:
            print("\n✅ Test PASSED - Runner executed successfully")
            return True
        else:
            print("\n❌ Test FAILED - Runner returned non-zero exit code")
            return False

    except subprocess.TimeoutExpired:
        print("\n⏱️  Test TIMEOUT - Runner took longer than 30 seconds")
        print("This is expected if the build actually runs (it takes 10-15 minutes)")
        print("To test with a real build, remove the timeout parameter")
        return False
    except Exception as e:
        print(f"\n❌ Test FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_runner()
    sys.exit(0 if success else 1)
