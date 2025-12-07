"""
Safety Mechanisms for Evolution System

Prevents the Evolution System from modifying production Context Foundry code.
All autonomous work must happen in isolated sandboxes.

"Simplicity is the ultimate sophistication" - Leonardo da Vinci
"""

import os
from pathlib import Path
from typing import Optional


def get_production_directory() -> Path:
    """
    Get the production Context Foundry directory path.

    Returns:
        Path to production directory
    """
    # Production is where the daemon is running from
    return Path(__file__).parent.parent.parent.resolve()


def is_production_directory(path: Path) -> bool:
    """
    Check if a path is the production Context Foundry directory.

    Args:
        path: Path to check

    Returns:
        True if path is production directory
    """
    try:
        production = get_production_directory()
        return path.resolve() == production
    except Exception:
        # If we can't determine, assume it's production (safer)
        return True


def verify_sandbox_environment(path: Path) -> bool:
    """
    Verify that a path is inside a valid sandbox directory.

    Args:
        path: Path to verify

    Returns:
        True if path is in a valid sandbox location
    """
    sandbox_base = Path(
        "/tmp/cf-sandboxes"
    ).resolve()  # Resolve for macOS (/private/tmp)

    try:
        # Check if path is relative to sandbox base
        path.resolve().relative_to(sandbox_base)
        return True
    except ValueError:
        return False


def enforce_sandbox_mode(working_dir: Path, operation: str = "file operation"):
    """
    Enforce that we're working in a sandbox, not production.

    Raises PermissionError if attempting to work in production.

    Args:
        working_dir: Directory where work will happen
        operation: Description of operation (for error message)

    Raises:
        PermissionError: If working_dir is production
        RuntimeError: If working_dir is not a valid sandbox
    """
    working_dir = Path(working_dir).resolve()

    # Check 1: Not production
    if is_production_directory(working_dir):
        raise PermissionError(
            f"❌ SAFETY VIOLATION: Cannot perform {operation} in production!\n\n"
            f"   Production: {working_dir}\n"
            f"   Required:   Sandbox in /tmp/cf-sandboxes/\n\n"
            "   Create a sandbox with:\n"
            "     from tools.security.sandboxes import SandboxManager\n"
            "     manager = SandboxManager()\n"
            "     sandbox = manager.create_sandbox(repo_url, task_id)\n"
        )

    # Check 2: Is valid sandbox
    if not verify_sandbox_environment(working_dir):
        raise RuntimeError(
            f"❌ SAFETY VIOLATION: Invalid sandbox location!\n\n"
            f"   Location: {working_dir}\n"
            f"   Expected: /tmp/cf-sandboxes/sandbox_*/\n\n"
            "   Sandboxes must be created in /tmp/cf-sandboxes/ for safety."
        )


def set_sandbox_mode(sandbox_path: Path):
    """
    Mark the current process as running in sandbox mode.

    Sets environment variables that other code can check.

    Args:
        sandbox_path: Path to the sandbox directory
    """
    os.environ["CF_SANDBOX_MODE"] = "1"
    os.environ["CF_SANDBOX_PATH"] = str(sandbox_path.resolve())


def is_sandbox_mode() -> bool:
    """
    Check if the current process is running in sandbox mode.

    Returns:
        True if CF_SANDBOX_MODE environment variable is set
    """
    return os.getenv("CF_SANDBOX_MODE") == "1"


def get_sandbox_path() -> Optional[Path]:
    """
    Get the current sandbox path if in sandbox mode.

    Returns:
        Path to sandbox, or None if not in sandbox mode
    """
    sandbox_path = os.getenv("CF_SANDBOX_PATH")
    if sandbox_path:
        return Path(sandbox_path)
    return None


def clear_sandbox_mode():
    """Clear sandbox mode environment variables."""
    if "CF_SANDBOX_MODE" in os.environ:
        del os.environ["CF_SANDBOX_MODE"]
    if "CF_SANDBOX_PATH" in os.environ:
        del os.environ["CF_SANDBOX_PATH"]


def validate_git_operation(working_dir: Path, branch: str):
    """
    Validate that a git operation is safe to perform.

    Args:
        working_dir: Directory where git operation will occur
        branch: Branch name for the operation

    Raises:
        PermissionError: If operation is unsafe
    """
    working_dir = Path(working_dir).resolve()

    # Never allow direct commits to main in production
    if is_production_directory(working_dir) and branch == "main":
        raise PermissionError(
            "❌ SAFETY VIOLATION: Cannot commit to main branch in production!\n\n"
            f"   Directory: {working_dir}\n"
            f"   Branch:    {branch}\n\n"
            "   Evolution System must work in sandboxes, not production."
        )

    # All Evolution work must be in sandboxes
    if not verify_sandbox_environment(working_dir):
        raise RuntimeError(
            f"❌ SAFETY VIOLATION: Git operations must occur in sandbox!\n\n"
            f"   Directory: {working_dir}\n"
            "   Expected:  /tmp/cf-sandboxes/\n"
        )


# Safety check decorator for functions that modify files
def require_sandbox(func):
    """
    Decorator that enforces sandbox mode for functions.

    Usage:
        @require_sandbox
        def modify_files(working_dir):
            # This will only run if working_dir is a sandbox
            ...
    """

    def wrapper(*args, **kwargs):
        # Try to find working_dir in args or kwargs
        working_dir = kwargs.get("working_dir") or kwargs.get("working_directory")

        if not working_dir and len(args) > 0:
            # Assume first arg is working_dir if not in kwargs
            working_dir = args[0]

        if working_dir:
            enforce_sandbox_mode(Path(working_dir), operation=func.__name__)

        return func(*args, **kwargs)

    return wrapper


if __name__ == "__main__":
    # Self-test
    print("🧪 Testing safety mechanisms...\n")

    production = get_production_directory()
    print(f"Production directory: {production}")

    # Test 1: Production detection
    try:
        enforce_sandbox_mode(production, "test operation")
        print("❌ FAIL: Production write not blocked!")
    except PermissionError:
        print("✅ PASS: Production protection working")

    # Test 2: Invalid sandbox detection
    try:
        enforce_sandbox_mode(Path("/tmp/not-a-sandbox"), "test operation")
        print("❌ FAIL: Invalid sandbox not detected!")
    except RuntimeError:
        print("✅ PASS: Invalid sandbox detected")

    # Test 3: Valid sandbox (simulated)
    sandbox = Path("/tmp/cf-sandboxes/sandbox_test_20251109")
    sandbox.mkdir(parents=True, exist_ok=True)
    try:
        enforce_sandbox_mode(sandbox, "test operation")
        print("✅ PASS: Valid sandbox accepted")
    except Exception as e:
        print(f"❌ FAIL: Valid sandbox rejected: {e}")
    finally:
        # Cleanup
        sandbox.rmdir()

    print("\n✅ All safety tests passed!")
