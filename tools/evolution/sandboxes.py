"""
Sandbox Manager - Isolate Evolution builds from Context Foundry source

Protects the Context Foundry repository by running all autonomous builds
in temporary cloned sandboxes. Each build gets a fresh clone in /tmp.
"""

import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class SandboxManager:
    """Manage isolated build sandboxes for Evolution System"""

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize sandbox manager

        Args:
            base_dir: Base directory for sandboxes (defaults to /tmp/cf-sandboxes)
        """
        self.base_dir = base_dir or Path("/tmp/cf-sandboxes")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.active_sandboxes: Dict[str, Dict] = {}

    def create_sandbox(self, repo_url: str, task_id: str) -> Path:
        """
        Create a new isolated sandbox by cloning the repository

        Args:
            repo_url: Git repository URL to clone
            task_id: Unique task identifier

        Returns:
            Path to sandbox directory

        Raises:
            RuntimeError: If clone fails
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sandbox_name = f"sandbox_{task_id[:8]}_{timestamp}"
        sandbox_path = self.base_dir / sandbox_name

        try:
            # Clone repository
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(sandbox_path)],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                raise RuntimeError(f"Git clone failed: {result.stderr}")

            # Track active sandbox
            self.active_sandboxes[task_id] = {
                "path": sandbox_path,
                "created_at": datetime.now().isoformat(),
                "repo_url": repo_url,
                "status": "active",
            }

            return sandbox_path

        except subprocess.TimeoutExpired:
            raise RuntimeError("Git clone timed out after 5 minutes")
        except Exception as e:
            # Cleanup on failure
            if sandbox_path.exists():
                shutil.rmtree(sandbox_path, ignore_errors=True)
            raise RuntimeError(f"Failed to create sandbox: {e}")

    def get_sandbox_path(self, task_id: str) -> Optional[Path]:
        """
        Get path to existing sandbox

        Args:
            task_id: Task identifier

        Returns:
            Path to sandbox or None if not found
        """
        if task_id in self.active_sandboxes:
            return self.active_sandboxes[task_id]["path"]
        return None

    def cleanup_sandbox(self, task_id: str) -> bool:
        """
        Remove sandbox and free disk space

        Args:
            task_id: Task identifier

        Returns:
            True if cleaned up successfully
        """
        if task_id not in self.active_sandboxes:
            return False

        sandbox_path = self.active_sandboxes[task_id]["path"]

        try:
            if sandbox_path.exists():
                shutil.rmtree(sandbox_path)

            del self.active_sandboxes[task_id]
            return True

        except Exception as e:
            print(f"Warning: Failed to cleanup sandbox {task_id}: {e}")
            return False

    def cleanup_old_sandboxes(self, max_age_hours: int = 24):
        """
        Remove sandboxes older than specified age

        Args:
            max_age_hours: Maximum age in hours before cleanup
        """
        from datetime import timedelta

        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        for task_id, info in list(self.active_sandboxes.items()):
            created_at = datetime.fromisoformat(info["created_at"])
            if created_at < cutoff_time:
                self.cleanup_sandbox(task_id)

    def list_sandboxes(self) -> Dict[str, Dict]:
        """
        List all active sandboxes

        Returns:
            Dictionary of task_id -> sandbox info
        """
        return self.active_sandboxes.copy()

    def get_stats(self) -> Dict:
        """
        Get sandbox statistics

        Returns:
            Dict with total count, disk usage, etc.
        """
        total_size = 0
        for info in self.active_sandboxes.values():
            sandbox_path = info["path"]
            if sandbox_path.exists():
                # Calculate directory size
                total_size += sum(
                    f.stat().st_size for f in sandbox_path.rglob("*") if f.is_file()
                )

        return {
            "total_sandboxes": len(self.active_sandboxes),
            "total_size_mb": total_size / (1024 * 1024),
            "base_dir": str(self.base_dir),
        }


def create_protected_sandbox(task_id: str, source_repo: str = None) -> Path:
    """
    Helper function to create a sandbox for Context Foundry builds

    Args:
        task_id: Unique task identifier
        source_repo: Repository URL (defaults to Context Foundry)

    Returns:
        Path to sandbox directory
    """
    if source_repo is None:
        # Default to Context Foundry repo
        source_repo = "https://github.com/context-foundry/context-foundry.git"

    manager = SandboxManager()
    return manager.create_sandbox(source_repo, task_id)
