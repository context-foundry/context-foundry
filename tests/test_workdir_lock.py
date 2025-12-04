"""
Tests for working directory lock management
"""

import os
from datetime import datetime


from context_foundry.daemon.workdir_lock import WorkDirLockManager, LockInfo


class TestWorkDirLockManager:
    """Test WorkDirLockManager functionality"""

    def test_acquire_and_release(self, tmp_path):
        """Test basic lock acquisition and release"""
        manager = WorkDirLockManager()

        # Acquire lock
        assert manager.acquire(tmp_path, "job1")

        # Verify lock is held
        is_locked, holder = manager.is_locked(tmp_path)
        assert is_locked
        assert holder == "job1"

        # Verify lockfile exists
        lockfile = tmp_path / WorkDirLockManager.LOCK_FILENAME
        assert lockfile.exists()

        # Release lock
        manager.release(tmp_path, "job1")

        # Verify lock is released
        is_locked, holder = manager.is_locked(tmp_path)
        assert not is_locked
        assert holder is None

        # Verify lockfile is removed
        assert not lockfile.exists()

    def test_concurrent_lock_rejection(self, tmp_path):
        """Test that concurrent lock acquisition is rejected"""
        manager = WorkDirLockManager()

        # First job acquires lock
        assert manager.acquire(tmp_path, "job1")

        # Second job tries to acquire - should fail
        assert not manager.acquire(tmp_path, "job2")

        # Verify first job still holds lock
        is_locked, holder = manager.is_locked(tmp_path)
        assert is_locked
        assert holder == "job1"

        # Release first job's lock
        manager.release(tmp_path, "job1")

        # Now second job can acquire
        assert manager.acquire(tmp_path, "job2")

        # Cleanup
        manager.release(tmp_path, "job2")

    def test_path_normalization(self, tmp_path):
        """Test that paths are normalized correctly"""
        manager = WorkDirLockManager()

        # Acquire with absolute path
        assert manager.acquire(tmp_path, "job1")

        # Try to acquire with relative path (same directory)
        # First, change to parent directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path.parent)
            relative_path = tmp_path.name

            # Should fail because same normalized path
            assert not manager.acquire(relative_path, "job2")

            # Verify original lock still held
            is_locked, holder = manager.is_locked(tmp_path)
            assert is_locked
            assert holder == "job1"
        finally:
            os.chdir(original_cwd)

        manager.release(tmp_path, "job1")

    def test_stale_lock_detection_dead_pid(self, tmp_path):
        """Test stale lock detection when PID no longer exists"""
        manager = WorkDirLockManager()

        # Create a fake lockfile with non-existent PID
        lockfile = tmp_path / WorkDirLockManager.LOCK_FILENAME
        fake_lock = LockInfo(
            job_id="old_job",
            pid=999999,  # Unlikely to exist
            locked_at="2024-01-01T00:00:00",
        )

        manager._write_lockfile(lockfile, fake_lock)

        # Try to acquire - should succeed by removing stale lock
        assert manager.acquire(tmp_path, "job1")

        # Verify new lock is held
        is_locked, holder = manager.is_locked(tmp_path)
        assert is_locked
        assert holder == "job1"

        manager.release(tmp_path, "job1")

    def test_stale_lock_detection_timeout(self, tmp_path):
        """Test stale lock detection based on timeout"""
        manager = WorkDirLockManager()

        # Create a fake lockfile with very old timestamp
        lockfile = tmp_path / WorkDirLockManager.LOCK_FILENAME
        old_lock = LockInfo(
            job_id="old_job",
            pid=os.getpid(),  # Current PID
            locked_at="2020-01-01T00:00:00",  # Very old
        )

        manager._write_lockfile(lockfile, old_lock)

        # Try to acquire - should succeed by removing stale lock
        assert manager.acquire(tmp_path, "job1")

        # Verify new lock is held
        is_locked, holder = manager.is_locked(tmp_path)
        assert is_locked
        assert holder == "job1"

        manager.release(tmp_path, "job1")

    def test_wrong_job_cannot_release_lock(self, tmp_path):
        """Test that a job cannot release another job's lock"""
        manager = WorkDirLockManager()

        # Job1 acquires lock
        assert manager.acquire(tmp_path, "job1")

        # Job2 tries to release - should be rejected
        manager.release(tmp_path, "job2")

        # Verify lock still held by job1
        is_locked, holder = manager.is_locked(tmp_path)
        assert is_locked
        assert holder == "job1"

        # Cleanup
        manager.release(tmp_path, "job1")

    def test_lockfile_survives_manager_restart(self, tmp_path):
        """Test that lockfile persists across manager instances"""
        # First manager acquires lock
        manager1 = WorkDirLockManager()
        assert manager1.acquire(tmp_path, "job1")

        # Create second manager (simulating daemon restart)
        manager2 = WorkDirLockManager()

        # Second manager should detect existing lock
        is_locked, holder = manager2.is_locked(tmp_path)
        assert is_locked
        assert holder == "job1"

        # Cleanup with first manager
        manager1.release(tmp_path, "job1")

    def test_cleanup_stale_locks(self, tmp_path):
        """Test cleanup_stale_locks removes stale locks"""
        manager = WorkDirLockManager()

        # Create multiple directories with locks
        dir1 = tmp_path / "proj1"
        dir2 = tmp_path / "proj2"
        dir3 = tmp_path / "proj3"

        for d in [dir1, dir2, dir3]:
            d.mkdir()

        # Acquire active lock in dir1
        assert manager.acquire(dir1, "job1")

        # Create stale lock in dir2 (dead PID)
        lockfile2 = dir2 / WorkDirLockManager.LOCK_FILENAME
        stale_lock = LockInfo(
            job_id="old_job2",
            pid=999998,
            locked_at="2024-01-01T00:00:00",
        )
        manager._write_lockfile(lockfile2, stale_lock)

        # Create stale lock in dir3 (old timestamp)
        lockfile3 = dir3 / WorkDirLockManager.LOCK_FILENAME
        old_lock = LockInfo(
            job_id="old_job3",
            pid=os.getpid(),
            locked_at="2020-01-01T00:00:00",
        )
        manager._write_lockfile(lockfile3, old_lock)

        # Add stale locks to in-memory tracking (simulating they were active before restart)
        manager._active_locks[manager.normalize_path(dir2)] = "old_job2"
        manager._active_locks[manager.normalize_path(dir3)] = "old_job3"

        # Run cleanup
        manager.cleanup_stale_locks()

        # Verify active lock still exists
        is_locked, holder = manager.is_locked(dir1)
        assert is_locked
        assert holder == "job1"

        # Verify stale locks are removed
        assert not lockfile2.exists()
        assert not lockfile3.exists()
        assert manager.normalize_path(dir2) not in manager._active_locks
        assert manager.normalize_path(dir3) not in manager._active_locks

        # Cleanup
        manager.release(dir1, "job1")

    def test_multiple_directories(self, tmp_path):
        """Test locking multiple different directories"""
        manager = WorkDirLockManager()

        dir1 = tmp_path / "proj1"
        dir2 = tmp_path / "proj2"
        dir1.mkdir()
        dir2.mkdir()

        # Acquire locks on different directories
        assert manager.acquire(dir1, "job1")
        assert manager.acquire(dir2, "job2")

        # Both should be locked
        is_locked1, holder1 = manager.is_locked(dir1)
        is_locked2, holder2 = manager.is_locked(dir2)

        assert is_locked1 and holder1 == "job1"
        assert is_locked2 and holder2 == "job2"

        # Release both
        manager.release(dir1, "job1")
        manager.release(dir2, "job2")

        # Both should be unlocked
        assert not manager.is_locked(dir1)[0]
        assert not manager.is_locked(dir2)[0]

    def test_startup_cleanup_with_working_directories(self, tmp_path):
        """Test that startup cleanup scans provided working directories for stale locks"""
        manager = WorkDirLockManager()

        # Create directories with stale lockfiles (simulating crashed daemon)
        dir1 = tmp_path / "crashed_proj1"
        dir2 = tmp_path / "crashed_proj2"
        dir3 = tmp_path / "active_proj"

        for d in [dir1, dir2, dir3]:
            d.mkdir()

        # Create stale lock in dir1 (dead PID)
        lockfile1 = dir1 / WorkDirLockManager.LOCK_FILENAME
        stale_lock1 = LockInfo(
            job_id="crashed_job1",
            pid=999991,  # Unlikely to exist
            locked_at="2024-01-01T00:00:00",
        )
        manager._write_lockfile(lockfile1, stale_lock1)

        # Create stale lock in dir2 (timeout)
        lockfile2 = dir2 / WorkDirLockManager.LOCK_FILENAME
        stale_lock2 = LockInfo(
            job_id="crashed_job2",
            pid=os.getpid(),
            locked_at="2020-01-01T00:00:00",  # Very old
        )
        manager._write_lockfile(lockfile2, stale_lock2)

        # Create active lock in dir3 (current PID, recent timestamp)
        lockfile3 = dir3 / WorkDirLockManager.LOCK_FILENAME
        active_lock = LockInfo(
            job_id="active_job",
            pid=os.getpid(),
            locked_at=datetime.now().isoformat(),
        )
        manager._write_lockfile(lockfile3, active_lock)

        # Simulate daemon startup: cleanup_stale_locks called with working directories
        # (In real usage, these would come from RUNNING/FAILED jobs in database)
        working_dirs = [str(dir1), str(dir2), str(dir3)]
        manager.cleanup_stale_locks(working_directories=working_dirs)

        # Verify stale locks were removed
        assert not lockfile1.exists(), "Stale lock (dead PID) should be removed"
        assert not lockfile2.exists(), "Stale lock (timeout) should be removed"

        # Verify active lock was preserved
        assert lockfile3.exists(), "Active lock should be preserved"
        is_locked, holder = manager.is_locked(dir3)
        assert is_locked
        assert holder == "active_job"

        # Cleanup
        manager._remove_lockfile(lockfile3)

    def test_startup_cleanup_without_working_directories(self, tmp_path):
        """Test that cleanup without working_directories only checks in-memory locks"""
        manager = WorkDirLockManager()

        # Create directory with orphaned lockfile
        orphaned_dir = tmp_path / "orphaned"
        orphaned_dir.mkdir()

        lockfile = orphaned_dir / WorkDirLockManager.LOCK_FILENAME
        orphaned_lock = LockInfo(
            job_id="orphaned_job",
            pid=999990,  # Dead PID
            locked_at="2024-01-01T00:00:00",
        )
        manager._write_lockfile(lockfile, orphaned_lock)

        # Call cleanup WITHOUT working_directories (simulating old behavior)
        manager.cleanup_stale_locks(working_directories=None)

        # Lockfile should still exist because we didn't tell cleanup where to look
        assert (
            lockfile.exists()
        ), "Orphaned lockfile not cleaned up without working_directories"

        # Now call cleanup WITH working_directories
        manager.cleanup_stale_locks(working_directories=[str(orphaned_dir)])

        # Now it should be cleaned up
        assert (
            not lockfile.exists()
        ), "Lockfile should be cleaned up when directory is provided"
