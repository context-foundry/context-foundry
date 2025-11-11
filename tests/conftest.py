"""
Pytest configuration and fixtures for Context Foundry tests.

This conftest.py sets up the test environment to ensure all tests
can run cleanly both locally and in CI.
"""

import os
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment(tmp_path_factory):
    """
    Set up the test environment for all tests.

    - Adds project root and tools/ to PYTHONPATH
    - Creates a temporary HOME directory to avoid permission issues
    - Ensures daemon tests can write to ~/.context-foundry/
    """
    # Get project root (parent of tests/)
    project_root = Path(__file__).parent.parent
    tools_dir = project_root / "tools"

    # Add to PYTHONPATH if not already present
    for path in [str(project_root), str(tools_dir)]:
        if path not in sys.path:
            sys.path.insert(0, path)

    # Set PYTHONPATH environment variable for subprocesses
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    paths_to_add = [str(project_root), str(tools_dir)]
    if current_pythonpath:
        paths_to_add.append(current_pythonpath)
    os.environ["PYTHONPATH"] = os.pathsep.join(paths_to_add)

    # Create a temporary HOME directory for the test session
    # This prevents permission errors when daemon tries to write logs
    temp_home = tmp_path_factory.mktemp("home")
    original_home = os.environ.get("HOME")

    # Set HOME to temp directory
    os.environ["HOME"] = str(temp_home)

    # Create .context-foundry directory structure
    context_foundry_dir = temp_home / ".context-foundry"
    context_foundry_dir.mkdir(parents=True, exist_ok=True)
    (context_foundry_dir / "logs").mkdir(exist_ok=True)
    (context_foundry_dir / "patterns").mkdir(exist_ok=True)

    yield

    # Restore original HOME after all tests complete
    if original_home:
        os.environ["HOME"] = original_home
    else:
        os.environ.pop("HOME", None)


@pytest.fixture
def temp_home(tmp_path):
    """
    Provide a temporary HOME directory for individual tests.

    Use this fixture when a test needs a clean HOME directory.
    """
    original_home = os.environ.get("HOME")
    os.environ["HOME"] = str(tmp_path)

    # Create basic .context-foundry structure
    context_foundry_dir = tmp_path / ".context-foundry"
    context_foundry_dir.mkdir(parents=True, exist_ok=True)

    yield tmp_path

    # Restore original HOME
    if original_home:
        os.environ["HOME"] = original_home
    else:
        os.environ.pop("HOME", None)
