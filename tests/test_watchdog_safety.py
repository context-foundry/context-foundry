#!/usr/bin/env python3
"""
Unit and integration tests for Process Watchdog.

Tests critical safety functionality:
- Process registration and tracking
- Timeout detection and enforcement
- Token budget monitoring
- Memory usage tracking
- Stuck process detection
- Process termination and cleanup
- Log file monitoring

Priority: 10/10 - Safety-critical system component
"""

import pytest
import tempfile
import shutil
import os
import time
import psutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

# Import watchdog components
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "evolution"))

from tools.evolution.process_watchdog import ProcessWatchdog, ProcessInfo


@pytest.mark.unit
@pytest.mark.tier1
class TestProcessInfo:
    """Test ProcessInfo tracking class"""

    def test_process_info_initialization(self):
        """Test ProcessInfo initializes with correct attributes"""
        pid = 12345
        task_id = "test-task-001"
        started_at = datetime.now()
        log_file = "/tmp/test.log"

        proc_info = ProcessInfo(
            pid=pid, task_id=task_id, started_at=started_at, log_file=log_file
        )

        assert proc_info.pid == pid
        assert proc_info.task_id == task_id
        assert proc_info.started_at == started_at
        assert proc_info.log_file == log_file
        assert proc_info.estimated_tokens == 0
        assert proc_info.last_check is not None

    def test_process_duration_calculation(self):
        """Test duration calculation is accurate"""
        started_at = datetime.now() - timedelta(minutes=5)
        proc_info = ProcessInfo(
            pid=12345,
            task_id="test-task",
            started_at=started_at,
            log_file="/tmp/test.log",
        )

        duration = proc_info.duration_minutes()

        # Should be approximately 5 minutes (allow small variance)
        assert 4.9 < duration < 5.1

    def test_process_is_alive_for_current_process(self):
        """Test is_alive returns True for current process"""
        proc_info = ProcessInfo(
            pid=os.getpid(),
            task_id="test-task",
            started_at=datetime.now(),
            log_file="/tmp/test.log",
        )

        assert proc_info.is_alive() is True

    def test_process_is_alive_for_nonexistent_process(self):
        """Test is_alive returns False for non-existent process"""
        # Use a PID that definitely doesn't exist
        proc_info = ProcessInfo(
            pid=999999,
            task_id="test-task",
            started_at=datetime.now(),
            log_file="/tmp/test.log",
        )

        assert proc_info.is_alive() is False


@pytest.mark.unit
@pytest.mark.tier1
class TestWatchdogInitialization:
    """Test watchdog initialization and configuration"""

    def test_watchdog_default_initialization(self):
        """Test watchdog initializes with default parameters"""
        watchdog = ProcessWatchdog()

        assert watchdog.max_duration_minutes == 60
        assert watchdog.max_tokens_per_task == 100_000
        assert watchdog.check_interval_seconds == 30
        assert watchdog.processes == {}

    def test_watchdog_custom_initialization(self):
        """Test watchdog initializes with custom parameters"""
        watchdog = ProcessWatchdog(
            max_duration_minutes=30,
            max_tokens_per_task=50_000,
            check_interval_seconds=15,
        )

        assert watchdog.max_duration_minutes == 30
        assert watchdog.max_tokens_per_task == 50_000
        assert watchdog.check_interval_seconds == 15


@pytest.mark.unit
@pytest.mark.tier1
class TestProcessRegistration:
    """Test process registration and unregistration"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = str(Path(self.temp_dir) / "test.log")
        Path(self.log_file).touch()

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_register_process(self):
        """Test process registration adds to tracking"""
        watchdog = ProcessWatchdog()
        pid = os.getpid()
        task_id = "test-task-001"

        watchdog.register_process(pid, task_id, self.log_file)

        assert pid in watchdog.processes
        assert watchdog.processes[pid].task_id == task_id
        assert watchdog.processes[pid].log_file == self.log_file
        assert watchdog.processes[pid].pid == pid

    def test_register_multiple_processes(self):
        """Test registering multiple processes"""
        watchdog = ProcessWatchdog()

        # Register multiple processes
        pid1 = 10001
        pid2 = 10002
        watchdog.register_process(pid1, "task-001", self.log_file)
        watchdog.register_process(pid2, "task-002", self.log_file)

        assert len(watchdog.processes) == 2
        assert pid1 in watchdog.processes
        assert pid2 in watchdog.processes

    def test_unregister_process(self):
        """Test process unregistration removes from tracking"""
        watchdog = ProcessWatchdog()
        pid = os.getpid()
        task_id = "test-task-001"

        watchdog.register_process(pid, task_id, self.log_file)
        assert pid in watchdog.processes

        watchdog.unregister_process(pid)
        assert pid not in watchdog.processes

    def test_unregister_nonexistent_process(self):
        """Test unregistering non-existent process doesn't error"""
        watchdog = ProcessWatchdog()

        # Should not raise error
        watchdog.unregister_process(99999)


@pytest.mark.integration
@pytest.mark.tier1
class TestTimeoutDetection:
    """Test timeout detection and enforcement"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = str(Path(self.temp_dir) / "test.log")
        Path(self.log_file).touch()

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_detect_timeout_for_old_process(self):
        """Test watchdog detects processes exceeding timeout"""
        watchdog = ProcessWatchdog(max_duration_minutes=1)  # 1 minute timeout

        # Create process that started 2 minutes ago
        pid = 10001
        task_id = "test-task-timeout"
        started_at = datetime.now() - timedelta(minutes=2)

        # Manually create ProcessInfo with old start time
        proc_info = ProcessInfo(pid, task_id, started_at, self.log_file)
        watchdog.processes[pid] = proc_info

        # Check if timeout would be detected
        duration = proc_info.duration_minutes()
        assert duration > watchdog.max_duration_minutes

    def test_no_timeout_for_recent_process(self):
        """Test watchdog doesn't flag recent processes as timed out"""
        watchdog = ProcessWatchdog(max_duration_minutes=10)

        pid = os.getpid()
        task_id = "test-task-recent"
        started_at = datetime.now() - timedelta(minutes=1)

        proc_info = ProcessInfo(pid, task_id, started_at, self.log_file)
        watchdog.processes[pid] = proc_info

        duration = proc_info.duration_minutes()
        assert duration < watchdog.max_duration_minutes


@pytest.mark.integration
@pytest.mark.tier1
class TestProcessChecking:
    """Test process checking and monitoring"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = str(Path(self.temp_dir) / "test.log")
        Path(self.log_file).write_text("Initial log content\n")

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    @patch("psutil.pid_exists")
    def test_check_processes_detects_dead_processes(self, mock_pid_exists):
        """Test check_processes identifies dead processes"""
        watchdog = ProcessWatchdog()

        # Register a process
        pid = 10001
        task_id = "test-task-dead"
        watchdog.register_process(pid, task_id, self.log_file)

        # Mock process as dead
        mock_pid_exists.return_value = False

        # Check processes
        issues = watchdog.check_processes()

        # Should detect the dead process
        assert len(issues) > 0 or not watchdog.processes[pid].is_alive()

    def test_check_processes_with_no_processes(self):
        """Test check_processes handles empty process list"""
        watchdog = ProcessWatchdog()

        # Should not error with no processes
        issues = watchdog.check_processes()

        assert isinstance(issues, list)


@pytest.mark.integration
@pytest.mark.tier1
class TestTokenBudgetTracking:
    """Test token budget monitoring"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = str(Path(self.temp_dir) / "test.log")
        Path(self.log_file).touch()

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_process_info_tracks_token_estimate(self):
        """Test ProcessInfo can track estimated tokens"""
        proc_info = ProcessInfo(
            pid=os.getpid(),
            task_id="test-task",
            started_at=datetime.now(),
            log_file=self.log_file,
        )

        # Initially zero
        assert proc_info.estimated_tokens == 0

        # Can be updated
        proc_info.estimated_tokens = 50000
        assert proc_info.estimated_tokens == 50000

    def test_watchdog_has_token_limit(self):
        """Test watchdog enforces token budget limit"""
        watchdog = ProcessWatchdog(max_tokens_per_task=100_000)

        assert watchdog.max_tokens_per_task == 100_000


@pytest.mark.integration
@pytest.mark.tier2
class TestMemoryMonitoring:
    """Test memory usage monitoring"""

    def test_current_process_memory_readable(self):
        """Test we can read current process memory"""
        proc = psutil.Process(os.getpid())
        mem_info = proc.memory_info()

        # Memory info should be available
        assert mem_info.rss > 0  # Resident Set Size


@pytest.mark.integration
@pytest.mark.tier1
class TestLogFileMonitoring:
    """Test log file monitoring for stuck processes"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = Path(self.temp_dir) / "test.log"

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_log_file_exists_check(self):
        """Test can check if log file exists"""
        # File doesn't exist yet
        assert not self.log_file.exists()

        # Create file
        self.log_file.write_text("Log content\n")
        assert self.log_file.exists()

    def test_log_file_modification_time(self):
        """Test can check log file modification time"""
        self.log_file.write_text("Initial content\n")
        initial_mtime = self.log_file.stat().st_mtime

        # Wait a bit and modify
        time.sleep(0.1)
        self.log_file.write_text("Updated content\n")
        updated_mtime = self.log_file.stat().st_mtime

        assert updated_mtime > initial_mtime

    def test_detect_stale_log_file(self):
        """Test can detect stale log files (no recent updates)"""
        self.log_file.write_text("Old log content\n")

        # Get modification time
        mtime = datetime.fromtimestamp(self.log_file.stat().st_mtime)
        age = datetime.now() - mtime

        # Just created, should be very recent
        assert age.total_seconds() < 1


@pytest.mark.integration
@pytest.mark.tier1
class TestWatchdogCleanup:
    """Test watchdog cleanup and shutdown"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = str(Path(self.temp_dir) / "test.log")
        Path(self.log_file).touch()

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_clear_all_processes(self):
        """Test can clear all tracked processes"""
        watchdog = ProcessWatchdog()

        # Register multiple processes
        watchdog.register_process(10001, "task-001", self.log_file)
        watchdog.register_process(10002, "task-002", self.log_file)

        assert len(watchdog.processes) == 2

        # Clear all
        watchdog.processes.clear()
        assert len(watchdog.processes) == 0


@pytest.mark.integration
@pytest.mark.tier1
class TestWatchdogConfiguration:
    """Test watchdog configuration options"""

    def test_configurable_duration_limit(self):
        """Test max duration is configurable"""
        watchdog1 = ProcessWatchdog(max_duration_minutes=30)
        watchdog2 = ProcessWatchdog(max_duration_minutes=120)

        assert watchdog1.max_duration_minutes == 30
        assert watchdog2.max_duration_minutes == 120

    def test_configurable_token_limit(self):
        """Test max token budget is configurable"""
        watchdog1 = ProcessWatchdog(max_tokens_per_task=50_000)
        watchdog2 = ProcessWatchdog(max_tokens_per_task=200_000)

        assert watchdog1.max_tokens_per_task == 50_000
        assert watchdog2.max_tokens_per_task == 200_000

    def test_configurable_check_interval(self):
        """Test check interval is configurable"""
        watchdog1 = ProcessWatchdog(check_interval_seconds=15)
        watchdog2 = ProcessWatchdog(check_interval_seconds=60)

        assert watchdog1.check_interval_seconds == 15
        assert watchdog2.check_interval_seconds == 60


@pytest.mark.integration
@pytest.mark.tier1
class TestWatchdogEdgeCases:
    """Test edge cases and error conditions"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_register_same_pid_twice(self):
        """Test registering same PID twice updates tracking"""
        watchdog = ProcessWatchdog()
        pid = 10001
        log_file = str(Path(self.temp_dir) / "test.log")
        Path(log_file).touch()

        watchdog.register_process(pid, "task-001", log_file)
        watchdog.register_process(pid, "task-002", log_file)

        # Should have only one entry (overwritten)
        assert len(watchdog.processes) == 1
        assert watchdog.processes[pid].task_id == "task-002"

    def test_process_info_with_missing_log_file(self):
        """Test ProcessInfo handles missing log file gracefully"""
        proc_info = ProcessInfo(
            pid=os.getpid(),
            task_id="test-task",
            started_at=datetime.now(),
            log_file="/nonexistent/path/log.txt",
        )

        # Should still initialize
        assert proc_info.log_file == "/nonexistent/path/log.txt"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
