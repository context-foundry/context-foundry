"""
Cross-Platform Utilities for Context Foundry

Provides platform-agnostic wrappers for:
- Process management (psutil)
- Shell command execution
- Path handling
- Claude CLI detection

Created as part of Phase 2: Windows Compatibility refactor.
"""

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

# psutil is optional but recommended for process management
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system() == "Windows"


def is_macos() -> bool:
    """Check if running on macOS."""
    return platform.system() == "Darwin"


def is_linux() -> bool:
    """Check if running on Linux."""
    return platform.system() == "Linux"


# =============================================================================
# Shell and Command Execution
# =============================================================================


def get_shell() -> List[str]:
    """
    Get the appropriate shell command prefix for the current platform.

    Returns:
        List of shell command parts for subprocess

    Example:
        >>> cmd = get_shell() + ["echo hello"]
        >>> subprocess.run(cmd, shell=False)
    """
    if is_windows():
        return ["cmd", "/c"]
    return ["/bin/bash", "-c"]


def get_shell_executable() -> str:
    """
    Get the shell executable path for the current platform.

    Returns:
        Path to shell executable
    """
    if is_windows():
        return os.environ.get("COMSPEC", "cmd.exe")
    return os.environ.get("SHELL", "/bin/bash")


def run_shell_command(
    command: str,
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
    timeout: Optional[int] = None,
    capture_output: bool = True,
) -> subprocess.CompletedProcess:
    """
    Run a shell command in a cross-platform way.

    Args:
        command: The command string to execute
        cwd: Working directory
        env: Environment variables (merged with current env)
        timeout: Timeout in seconds
        capture_output: Whether to capture stdout/stderr

    Returns:
        CompletedProcess with returncode, stdout, stderr
    """
    # Merge environment
    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    # Build command
    if is_windows():
        # On Windows, use shell=True for complex commands
        return subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            env=run_env,
            timeout=timeout,
            capture_output=capture_output,
            text=True,
        )
    else:
        # On Unix, use bash explicitly
        return subprocess.run(
            ["/bin/bash", "-c", command],
            cwd=cwd,
            env=run_env,
            timeout=timeout,
            capture_output=capture_output,
            text=True,
        )


# =============================================================================
# Claude CLI Detection
# =============================================================================


def find_claude_cli() -> Optional[str]:
    """
    Find the Claude CLI executable in PATH.

    Returns:
        Path to claude executable, or None if not found
    """
    # Try common names
    for name in ["claude", "claude.exe"]:
        path = shutil.which(name)
        if path:
            return path
    return None


def ensure_claude_cli() -> str:
    """
    Ensure Claude CLI is available, raising an error if not.

    Returns:
        Path to claude executable

    Raises:
        RuntimeError: If Claude CLI is not found
    """
    path = find_claude_cli()
    if not path:
        raise RuntimeError(
            "Claude CLI not found in PATH. "
            "Please install it from https://claude.ai/download"
        )
    return path


def get_claude_command() -> List[str]:
    """
    Get the Claude CLI command as a list for subprocess.

    Returns:
        List with claude executable path
    """
    return [ensure_claude_cli()]


# =============================================================================
# Process Management (psutil wrappers)
# =============================================================================


def kill_process_tree(pid: int, timeout: int = 5) -> Tuple[List[int], List[int]]:
    """
    Kill a process and all its children in a cross-platform way.

    Args:
        pid: Process ID to kill
        timeout: Seconds to wait for graceful termination

    Returns:
        Tuple of (killed_pids, failed_pids)
    """
    if not PSUTIL_AVAILABLE:
        # Fallback: just try to kill the main process
        try:
            os.kill(pid, 9)  # SIGKILL
            return ([pid], [])
        except (ProcessLookupError, PermissionError):
            return ([], [pid])

    killed = []
    failed = []

    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)

        # Terminate children first, then parent
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass

        try:
            parent.terminate()
        except psutil.NoSuchProcess:
            pass

        # Wait for graceful shutdown
        gone, alive = psutil.wait_procs(children + [parent], timeout=timeout)
        killed.extend([p.pid for p in gone])

        # Force kill any remaining
        for p in alive:
            try:
                p.kill()
                killed.append(p.pid)
            except psutil.NoSuchProcess:
                killed.append(p.pid)
            except (psutil.AccessDenied, PermissionError):
                failed.append(p.pid)

    except psutil.NoSuchProcess:
        # Process already gone
        killed.append(pid)
    except (psutil.AccessDenied, PermissionError):
        failed.append(pid)

    return (killed, failed)


def is_process_running(pid: int) -> bool:
    """
    Check if a process is still running.

    Args:
        pid: Process ID to check

    Returns:
        True if process exists and is running
    """
    if not PSUTIL_AVAILABLE:
        try:
            os.kill(pid, 0)  # Signal 0 = check existence
            return True
        except (ProcessLookupError, PermissionError):
            return False

    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def get_process_children(pid: int) -> List[int]:
    """
    Get all child process IDs of a process.

    Args:
        pid: Parent process ID

    Returns:
        List of child PIDs
    """
    if not PSUTIL_AVAILABLE:
        return []

    try:
        parent = psutil.Process(pid)
        return [child.pid for child in parent.children(recursive=True)]
    except psutil.NoSuchProcess:
        return []


def terminate_process_gracefully(
    pid: int, timeout: int = 5, force: bool = True
) -> bool:
    """
    Terminate a process gracefully, optionally forcing if it doesn't stop.

    Args:
        pid: Process ID
        timeout: Seconds to wait for graceful termination
        force: Whether to force kill if graceful fails

    Returns:
        True if process was terminated
    """
    if not PSUTIL_AVAILABLE:
        try:
            os.kill(pid, 15)  # SIGTERM
            return True
        except (ProcessLookupError, PermissionError):
            return False

    try:
        proc = psutil.Process(pid)
        proc.terminate()

        try:
            proc.wait(timeout=timeout)
            return True
        except psutil.TimeoutExpired:
            if force:
                proc.kill()
                return True
            return False

    except psutil.NoSuchProcess:
        return True  # Already gone
    except (psutil.AccessDenied, PermissionError):
        return False


# =============================================================================
# Path Utilities
# =============================================================================


def get_home_dir() -> Path:
    """Get user's home directory cross-platform."""
    return Path.home()


def get_context_foundry_dir() -> Path:
    """Get the .context-foundry directory in user's home."""
    return get_home_dir() / ".context-foundry"


def ensure_context_foundry_dir() -> Path:
    """Ensure .context-foundry directory exists and return path."""
    cf_dir = get_context_foundry_dir()
    cf_dir.mkdir(parents=True, exist_ok=True)
    return cf_dir


def normalize_path(path: str) -> str:
    """
    Normalize path separators to forward slashes.

    This is useful for consistent path representation in logs/output
    while actual file operations should use pathlib.

    Args:
        path: Path string with any separator style

    Returns:
        Path with forward slashes
    """
    return path.replace("\\", "/")


def to_native_path(path: str) -> str:
    """
    Convert path to native OS separator.

    Args:
        path: Path string

    Returns:
        Path with native separators
    """
    return str(Path(path))


# =============================================================================
# Environment Detection
# =============================================================================


def get_platform_info() -> dict:
    """
    Get detailed platform information for debugging.

    Returns:
        Dict with platform details
    """
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "is_windows": is_windows(),
        "is_macos": is_macos(),
        "is_linux": is_linux(),
        "psutil_available": PSUTIL_AVAILABLE,
        "claude_cli": find_claude_cli(),
    }


def check_platform_compatibility() -> List[str]:
    """
    Check for potential platform compatibility issues.

    Returns:
        List of warning messages (empty if all OK)
    """
    warnings = []

    if not PSUTIL_AVAILABLE:
        warnings.append(
            "psutil not installed - process management will be limited. "
            "Install with: pip install psutil"
        )

    if not find_claude_cli():
        warnings.append(
            "Claude CLI not found in PATH. Install from https://claude.ai/download"
        )

    if is_windows():
        # Check for common Windows issues
        if "COMSPEC" not in os.environ:
            warnings.append("COMSPEC environment variable not set")

    return warnings
