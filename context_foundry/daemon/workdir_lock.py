"""
Working Directory Lock for Context Foundry Daemon

Prevents concurrent builds in the same working directory using:
1. In-memory locks (for single daemon instance)
2. Disk-based lockfiles with PID checking (survives daemon restarts)
"""

import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Union

logger = logging.getLogger(__name__)


@dataclass
class LockInfo:
    """Information about a working directory lock"""

    job_id: str
    pid: int
    locked_at: str  # ISO format timestamp
    daemon_version: str = "1.0"


class WorkDirLockManager:
    """
    Manages working directory locks to prevent concurrent builds

    Features:
    - In-memory lock tracking for current daemon instance
    - Disk-based lockfiles (.cfd-lock) for restart resilience
    - Stale lock detection (PID no longer exists)
    - Automatic cleanup on job completion or failure
    """

    LOCK_FILENAME = ".cfd-lock"
    LOCK_TIMEOUT_SECONDS = 3600  # 1 hour - consider stale after this

    def __init__(self):
        """Initialize WorkDirLockManager"""
        # In-memory map: {normalized_path: job_id}
        self._active_locks: Dict[Path, str] = {}
        self._lock = threading.Lock()

        logger.info("WorkDirLockManager initialized")

    def normalize_path(self, path: Union[str, Path]) -> Path:
        """
        Normalize a working directory path

        Args:
            path: Working directory path

        Returns:
            Normalized absolute Path
        """
        return Path(path).resolve()

    def _is_process_running(self, pid: int) -> bool:
        """
        Check if a process with given PID exists

        Args:
            pid: Process ID to check

        Returns:
            True if process exists, False otherwise
        """
        try:
            # Signal 0 checks if process exists without sending actual signal
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _read_lockfile(self, lockfile_path: Path) -> Optional[LockInfo]:
        """
        Read and parse a lockfile

        Args:
            lockfile_path: Path to lockfile

        Returns:
            LockInfo if valid, None if missing or invalid
        """
        try:
            if not lockfile_path.exists():
                return None

            with open(lockfile_path, "r") as f:
                data = json.load(f)

            return LockInfo(
                job_id=data["job_id"],
                pid=data["pid"],
                locked_at=data["locked_at"],
                daemon_version=data.get("daemon_version", "unknown"),
            )
        except Exception as e:
            logger.warning(f"Failed to read lockfile {lockfile_path}: {e}")
            return None

    def _write_lockfile(self, lockfile_path: Path, lock_info: LockInfo):
        """
        Write a lockfile

        Args:
            lockfile_path: Path to lockfile
            lock_info: Lock information to write
        """
        try:
            # Ensure parent directory exists
            lockfile_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "job_id": lock_info.job_id,
                "pid": lock_info.pid,
                "locked_at": lock_info.locked_at,
                "daemon_version": lock_info.daemon_version,
            }

            with open(lockfile_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Lockfile created: {lockfile_path}")
        except Exception as e:
            logger.error(f"Failed to write lockfile {lockfile_path}: {e}")
            raise

    def _remove_lockfile(self, lockfile_path: Path):
        """
        Remove a lockfile

        Args:
            lockfile_path: Path to lockfile
        """
        try:
            if lockfile_path.exists():
                lockfile_path.unlink()
                logger.debug(f"Lockfile removed: {lockfile_path}")
        except Exception as e:
            logger.warning(f"Failed to remove lockfile {lockfile_path}: {e}")

    def _is_lock_stale(self, lock_info: LockInfo) -> tuple[bool, str]:
        """
        Check if a lock is stale

        Args:
            lock_info: Lock information to check

        Returns:
            Tuple of (is_stale: bool, reason: str)
        """
        # Check if process is still running
        if not self._is_process_running(lock_info.pid):
            return True, f"Process {lock_info.pid} no longer exists"

        # Check timeout
        try:
            locked_time = datetime.fromisoformat(lock_info.locked_at)
            age_seconds = (datetime.now() - locked_time).total_seconds()

            if age_seconds > self.LOCK_TIMEOUT_SECONDS:
                return (
                    True,
                    f"Lock age ({age_seconds:.0f}s) exceeds timeout ({self.LOCK_TIMEOUT_SECONDS}s)",
                )
        except Exception as e:
            logger.warning(f"Failed to parse lock timestamp: {e}")
            # If we can't parse the timestamp, consider it stale
            return True, f"Invalid timestamp: {e}"

        return False, ""

    def acquire(self, working_dir: Union[str, Path], job_id: str) -> bool:
        """
        Acquire a lock on a working directory

        Args:
            working_dir: Working directory to lock
            job_id: Job ID requesting the lock

        Returns:
            True if lock acquired successfully, False if directory is already locked

        Raises:
            RuntimeError: If unable to create lockfile
        """
        norm_path = self.normalize_path(working_dir)
        lockfile_path = norm_path / self.LOCK_FILENAME

        with self._lock:
            # Check in-memory locks first
            if norm_path in self._active_locks:
                existing_job = self._active_locks[norm_path]
                logger.warning(
                    f"Working directory {norm_path} already locked by job {existing_job}"
                )
                return False

            # Check disk-based lockfile
            lock_info = self._read_lockfile(lockfile_path)
            if lock_info:
                # Check if lock is stale
                is_stale, reason = self._is_lock_stale(lock_info)

                if is_stale:
                    logger.warning(
                        f"Stale lock detected for {norm_path}: {reason}. Removing."
                    )
                    self._remove_lockfile(lockfile_path)
                else:
                    # Lock is active
                    logger.warning(
                        f"Working directory {norm_path} locked by job {lock_info.job_id} "
                        f"(PID {lock_info.pid}, locked at {lock_info.locked_at})"
                    )
                    return False

            # Acquire lock
            new_lock = LockInfo(
                job_id=job_id,
                pid=os.getpid(),
                locked_at=datetime.now().isoformat(),
            )

            # Write lockfile
            self._write_lockfile(lockfile_path, new_lock)

            # Add to in-memory tracking
            self._active_locks[norm_path] = job_id

            logger.info(f"Lock acquired for {norm_path} by job {job_id}")
            return True

    def release(self, working_dir: Union[str, Path], job_id: str):
        """
        Release a lock on a working directory

        Args:
            working_dir: Working directory to unlock
            job_id: Job ID releasing the lock (for verification)
        """
        norm_path = self.normalize_path(working_dir)
        lockfile_path = norm_path / self.LOCK_FILENAME

        with self._lock:
            # Check if we hold this lock
            current_holder = self._active_locks.get(norm_path)

            if current_holder != job_id:
                logger.warning(
                    f"Job {job_id} attempted to release lock for {norm_path}, "
                    f"but lock is held by {current_holder}"
                )
                return

            # Remove from in-memory tracking
            del self._active_locks[norm_path]

            # Remove lockfile
            self._remove_lockfile(lockfile_path)

            logger.info(f"Lock released for {norm_path} by job {job_id}")

    def is_locked(self, working_dir: Union[str, Path]) -> tuple[bool, Optional[str]]:
        """
        Check if a working directory is locked

        Args:
            working_dir: Working directory to check

        Returns:
            Tuple of (is_locked: bool, job_id: Optional[str])
        """
        norm_path = self.normalize_path(working_dir)

        with self._lock:
            # Check in-memory first
            if norm_path in self._active_locks:
                return True, self._active_locks[norm_path]

        # Check disk-based lockfile
        lockfile_path = norm_path / self.LOCK_FILENAME
        lock_info = self._read_lockfile(lockfile_path)

        if lock_info:
            is_stale, _ = self._is_lock_stale(lock_info)
            if not is_stale:
                return True, lock_info.job_id

        return False, None

    def cleanup_stale_locks(
        self, working_directories: Optional[List[Union[str, Path]]] = None
    ):
        """
        Clean up all stale locks (called on daemon startup)

        This scans both in-memory locks AND disk-based lockfiles.

        Args:
            working_directories: List of working directories to check for stale locks.
                                If None, only checks in-memory locks (limited usefulness).
                                On daemon startup, pass list of directories from RUNNING jobs.
        """
        with self._lock:
            stale_paths = []
            checked_paths = set()

            # First, check in-memory locks
            for path in list(self._active_locks.keys()):
                checked_paths.add(path)
                lockfile_path = path / self.LOCK_FILENAME
                lock_info = self._read_lockfile(lockfile_path)

                if lock_info:
                    is_stale, reason = self._is_lock_stale(lock_info)
                    if is_stale:
                        logger.info(f"Removing stale lock for {path}: {reason}")
                        self._remove_lockfile(lockfile_path)
                        stale_paths.append(path)
                else:
                    # Lockfile missing but in-memory lock exists (shouldn't happen)
                    logger.warning(f"In-memory lock for {path} has no lockfile")
                    stale_paths.append(path)

            # Second, check disk-based lockfiles from provided working directories
            # This is crucial for daemon startup when in-memory locks are empty
            if working_directories:
                for workdir in working_directories:
                    norm_path = self.normalize_path(workdir)

                    # Skip if already checked via in-memory locks
                    if norm_path in checked_paths:
                        continue

                    checked_paths.add(norm_path)
                    lockfile_path = norm_path / self.LOCK_FILENAME

                    if not lockfile_path.exists():
                        continue

                    lock_info = self._read_lockfile(lockfile_path)
                    if not lock_info:
                        # Corrupted lockfile - remove it
                        logger.warning(f"Removing corrupted lockfile: {lockfile_path}")
                        self._remove_lockfile(lockfile_path)
                        continue

                    is_stale, reason = self._is_lock_stale(lock_info)
                    if is_stale:
                        logger.info(f"Removing stale lock for {norm_path}: {reason}")
                        self._remove_lockfile(lockfile_path)
                        stale_paths.append(norm_path)

            # Remove from in-memory tracking
            for path in stale_paths:
                if path in self._active_locks:
                    del self._active_locks[path]

            if stale_paths:
                logger.info(f"Cleaned up {len(stale_paths)} stale locks")
            else:
                logger.debug("No stale locks found")
