"""
Zombie Process Detection and Cleanup

Identifies and manages orphaned/stuck processes related to Context Foundry.
"""

import os
import signal
import time
from typing import List, Optional

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class ZombieProcess:
    """Represents a potentially orphaned process"""

    def __init__(
        self, pid: int, name: str, cmdline: str, age_seconds: float, reason: str
    ):
        self.pid = pid
        self.name = name
        self.cmdline = cmdline
        self.age_seconds = age_seconds
        self.reason = reason

    def __repr__(self):
        return f"ZombieProcess(pid={self.pid}, name={self.name}, age={self.age_seconds:.0f}s)"


def find_zombies(exclude_pids: Optional[List[int]] = None) -> List[ZombieProcess]:
    """
    Find potentially orphaned Context Foundry processes.

    Args:
        exclude_pids: PIDs to exclude from detection (e.g., current process)

    Returns:
        List of ZombieProcess objects
    """
    if not PSUTIL_AVAILABLE:
        return []

    if exclude_pids is None:
        exclude_pids = []

    # Always exclude current process and its parents
    current_pid = os.getpid()
    exclude_pids.append(current_pid)

    try:
        current_proc = psutil.Process(current_pid)
        for parent in current_proc.parents():
            exclude_pids.append(parent.pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

    zombies = []
    current_time = time.time()

    # Patterns to detect
    patterns = {
        "cfd_daemon": ["daemon.py", "cfd"],
        "claude": ["claude"],
        "autonomous_build": ["autonomous_build", "tmpd", "tmp"],  # temp scripts
        "mcp_server": ["mcp_server.py"],
    }

    for proc in psutil.process_iter(
        ["pid", "name", "cmdline", "create_time", "status"]
    ):
        try:
            pid = proc.info["pid"]

            # Skip excluded PIDs
            if pid in exclude_pids:
                continue

            # Skip if no cmdline (kernel processes)
            cmdline = proc.info.get("cmdline")
            if not cmdline:
                continue

            cmdline_str = " ".join(cmdline)
            name = proc.info.get("name", "")

            # Check if matches any pattern
            matched_type = None
            for proc_type, keywords in patterns.items():
                if any(
                    keyword in cmdline_str or keyword in name for keyword in keywords
                ):
                    matched_type = proc_type
                    break

            if not matched_type:
                continue

            # Calculate age
            create_time = proc.info.get("create_time", current_time)
            age_seconds = current_time - create_time

            # Determine reason
            reason = _classify_zombie(proc, matched_type, age_seconds)

            if reason:
                zombies.append(
                    ZombieProcess(
                        pid=pid,
                        name=name,
                        cmdline=cmdline_str[:100],  # Truncate long cmdlines
                        age_seconds=age_seconds,
                        reason=reason,
                    )
                )

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return zombies


def _classify_zombie(
    proc: psutil.Process, proc_type: str, age_seconds: float
) -> Optional[str]:
    """
    Classify if a process is a zombie and why.

    Returns:
        Reason string if zombie, None otherwise
    """
    # Old daemon (>1 day)
    if proc_type == "cfd_daemon" and age_seconds > 86400:
        return f"Old daemon (running {age_seconds/3600:.1f}h)"

    # Stuck Claude (>2 hours)
    if proc_type == "claude" and age_seconds > 7200:
        return f"Stuck Claude instance ({age_seconds/3600:.1f}h)"

    # Orphaned build script (>3 hours)
    if proc_type == "autonomous_build" and age_seconds > 10800:
        return f"Orphaned build script ({age_seconds/3600:.1f}h)"

    # Orphaned MCP server (>2 hours)
    if proc_type == "mcp_server" and age_seconds > 7200:
        return f"Orphaned MCP server ({age_seconds/3600:.1f}h)"

    return None


def kill_process(pid: int, force: bool = False) -> bool:
    """
    Kill a process safely.

    Args:
        pid: Process ID to kill
        force: If True, use SIGKILL. Otherwise use SIGTERM.

    Returns:
        True if successful, False otherwise
    """
    if not PSUTIL_AVAILABLE:
        # Fallback to os.kill
        try:
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    try:
        proc = psutil.Process(pid)

        if force:
            proc.kill()
        else:
            proc.terminate()

            # Wait up to 5 seconds for graceful termination
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                # Force kill if didn't terminate
                proc.kill()

        return True

    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def format_zombie_list(zombies: List[ZombieProcess]) -> str:
    """
    Format zombie list for display.

    Returns:
        Formatted string
    """
    if not zombies:
        return "No zombie processes detected"

    lines = []
    lines.append(f"\n{'PID':<8} {'Name':<20} {'Age':<12} {'Reason':<40}")
    lines.append("-" * 80)

    for zombie in zombies:
        age_str = _format_age(zombie.age_seconds)
        lines.append(
            f"{zombie.pid:<8} {zombie.name[:20]:<20} {age_str:<12} {zombie.reason:<40}"
        )

    return "\n".join(lines)


def _format_age(seconds: float) -> str:
    """Format age in human-readable format"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.0f}m"
    elif seconds < 86400:
        return f"{seconds/3600:.1f}h"
    else:
        return f"{seconds/86400:.1f}d"
