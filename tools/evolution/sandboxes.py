"""
Sandbox Manager - Isolate Evolution builds from Context Foundry source

Protects the Context Foundry repository by running all autonomous builds
in temporary cloned sandboxes. Each build gets a fresh clone in /tmp.
"""

import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


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

        logger.info(f"🏗️  Creating sandbox for task {task_id[:8]}")
        logger.info(f"   Repository: {repo_url}")
        logger.info(f"   Path: {sandbox_path}")

        try:
            # Clone repository
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(sandbox_path)],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                logger.error(f"❌ Git clone failed for {task_id[:8]}: {result.stderr}")
                raise RuntimeError(f"Git clone failed: {result.stderr}")

            # Track active sandbox
            self.active_sandboxes[task_id] = {
                "path": sandbox_path,
                "created_at": datetime.now().isoformat(),
                "repo_url": repo_url,
                "status": "active",
            }

            logger.info(f"✅ Sandbox created successfully: {sandbox_path}")
            return sandbox_path

        except subprocess.TimeoutExpired:
            logger.error(f"❌ Git clone timed out for {task_id[:8]} after 5 minutes")
            raise RuntimeError("Git clone timed out after 5 minutes")
        except Exception as e:
            # Cleanup on failure
            if sandbox_path.exists():
                shutil.rmtree(sandbox_path, ignore_errors=True)
            logger.error(f"❌ Failed to create sandbox for {task_id[:8]}: {e}")
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

    def cleanup_sandbox(self, task_id: str = None, sandbox_path: Path = None) -> bool:
        """
        Remove sandbox and free disk space

        Can cleanup by task_id (if sandbox was created by this instance) or by
        direct path (for cleanup across different SandboxManager instances).

        Args:
            task_id: Task identifier (optional if sandbox_path provided)
            sandbox_path: Direct path to sandbox (optional if task_id provided)

        Returns:
            True if cleaned up successfully
        """
        if task_id and task_id in self.active_sandboxes:
            # Cleanup from active_sandboxes (sandbox created by this instance)
            sandbox_path = self.active_sandboxes[task_id]["path"]
            logger.info(f"🧹 Cleaning up sandbox for task {task_id[:8]}: {sandbox_path}")

            try:
                if sandbox_path.exists():
                    shutil.rmtree(sandbox_path)
                    logger.info(f"✅ Sandbox directory removed: {sandbox_path}")

                del self.active_sandboxes[task_id]
                logger.info(f"✅ Sandbox cleanup complete for task {task_id[:8]}")
                return True

            except Exception as e:
                logger.error(f"❌ Failed to cleanup sandbox {task_id[:8]}: {e}")
                return False

        elif sandbox_path:
            # Direct path cleanup (for cross-instance cleanup)
            sandbox_path = Path(sandbox_path)

            # Verify it's a sandbox path for safety
            if not sandbox_path.name.startswith("sandbox_"):
                logger.error(f"❌ Refusing to delete non-sandbox path: {sandbox_path}")
                return False

            if not str(sandbox_path.resolve()).startswith(str(self.base_dir.resolve())):
                logger.error(f"❌ Refusing to delete path outside sandbox base: {sandbox_path}")
                return False

            logger.info(f"🧹 Cleaning up sandbox by path: {sandbox_path}")

            try:
                if sandbox_path.exists():
                    shutil.rmtree(sandbox_path)
                    logger.info(f"✅ Sandbox directory removed: {sandbox_path}")
                    return True
                else:
                    logger.warning(f"Sandbox path does not exist: {sandbox_path}")
                    return False

            except Exception as e:
                logger.error(f"❌ Failed to cleanup sandbox at {sandbox_path}: {e}")
                return False
        else:
            logger.error("cleanup_sandbox() requires either task_id or sandbox_path")
            return False

    def cleanup_old_sandboxes(self, max_age_hours: int = 24) -> int:
        """
        Remove sandboxes older than specified age

        Scans the filesystem directly to find orphaned sandboxes that may have
        been left behind by daemon crashes or process kills.

        Args:
            max_age_hours: Maximum age in hours before cleanup

        Returns:
            Number of sandboxes cleaned up
        """
        import time

        if not self.base_dir.exists():
            return 0

        cutoff_time = time.time() - (max_age_hours * 3600)
        cleaned_count = 0

        # Scan filesystem for sandbox directories
        for sandbox_dir in self.base_dir.iterdir():
            if not sandbox_dir.is_dir():
                continue

            if not sandbox_dir.name.startswith("sandbox_"):
                continue

            try:
                # Check modification time (last time directory was modified)
                mtime = sandbox_dir.stat().st_mtime

                if mtime < cutoff_time:
                    # Old sandbox - clean it up
                    shutil.rmtree(sandbox_dir, ignore_errors=True)
                    cleaned_count += 1

                    # Also remove from active_sandboxes if present
                    for task_id, info in list(self.active_sandboxes.items()):
                        if info["path"] == sandbox_dir:
                            del self.active_sandboxes[task_id]
                            break

            except Exception as e:
                # Log but continue with other sandboxes
                logger.warning(
                    f"Failed to check/cleanup sandbox {sandbox_dir.name}: {e}"
                )

        return cleaned_count

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
