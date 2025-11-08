"""Tests for TUI data provider functionality"""

import asyncio
import tempfile
import pytest
from pathlib import Path
from datetime import datetime
import json

from tools.tui.data.provider import TUIDataProvider
from tools.tui.config import TUIConfig


class TestTUIDataProvider:
    """Test suite for TUIDataProvider"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config(self, temp_dir):
        """Create a test TUIConfig"""
        config = TUIConfig()
        # Override default paths with temp directory
        config.project_dirs = [temp_dir]
        return config

    @pytest.fixture
    def provider(self, config):
        """Create a TUIDataProvider instance"""
        return TUIDataProvider(config)

    @pytest.mark.asyncio
    async def test_get_build_logs_from_file(self, provider, temp_dir):
        """Test reading build logs from a .launch-{session_id}.log file"""
        # Create a test session ID
        session_id = "test-session-123"

        # Add temp_dir to tracked builds
        provider._tracked_builds = [str(temp_dir)]

        # Create a mock log file
        log_file = temp_dir / f".launch-{session_id}.log"
        log_content = """[INFO] Build started: test-session-123
[INFO] Scout phase: Analyzing requirements...
[INFO] Architect phase: Designing system...
[INFO] Builder phase: Implementing code...
[SUCCESS] Build completed successfully
"""
        log_file.write_text(log_content)

        # Get logs
        logs = await provider.get_build_logs(session_id)

        # Verify logs were read correctly
        assert len(logs) == 5
        assert logs[0] == "[INFO] Build started: test-session-123"
        assert logs[1] == "[INFO] Scout phase: Analyzing requirements..."
        assert logs[4] == "[SUCCESS] Build completed successfully"

    @pytest.mark.asyncio
    async def test_get_build_logs_no_file(self, provider):
        """Test behavior when no log file exists"""
        session_id = "non-existent-session"

        logs = await provider.get_build_logs(session_id)

        # Should return helpful message
        assert len(logs) >= 1
        assert "No logs found" in logs[0]

    @pytest.mark.asyncio
    async def test_get_build_logs_from_daemon_log(self, provider, temp_dir):
        """Test reading logs from the global daemon.log when session-specific log doesn't exist"""
        session_id = "daemon-session-456"

        # Create mock daemon log directory
        daemon_log_dir = Path.home() / '.context-foundry' / 'evolution' / 'logs'
        daemon_log_file = daemon_log_dir / 'daemon.log'

        # Only run this test if we can write to the daemon log location
        if daemon_log_dir.exists() or daemon_log_dir.parent.exists():
            try:
                daemon_log_dir.mkdir(parents=True, exist_ok=True)

                # Backup existing daemon.log if it exists
                backup_content = None
                if daemon_log_file.exists():
                    backup_content = daemon_log_file.read_text()

                try:
                    # Create mock daemon log with session-specific entries
                    daemon_content = f"""2025-11-07 18:50:32,270 - __main__ - INFO - Starting Evolution Daemon
2025-11-07 18:52:35,294 - __main__ - INFO - Picked up task: {session_id}
2025-11-07 18:52:35,295 - __main__ - INFO - Executing task {session_id}
2025-11-07 18:52:35,295 - __main__ - INFO - Task {session_id} completed successfully
"""
                    daemon_log_file.write_text(daemon_content)

                    # Get logs
                    logs = await provider.get_build_logs(session_id)

                    # Verify we got session-specific logs from daemon.log
                    assert len(logs) > 0
                    # All returned logs should contain the session_id since we filter for it
                    assert all(session_id in log for log in logs), f"Some logs don't contain session_id: {logs}"

                finally:
                    # Restore original daemon.log
                    if backup_content is not None:
                        daemon_log_file.write_text(backup_content)
                    elif daemon_log_file.exists():
                        daemon_log_file.unlink()

            except (OSError, PermissionError):
                # Skip test if we can't write to daemon log location
                pytest.skip("Cannot write to daemon log location")
        else:
            pytest.skip("Daemon log directory does not exist")

    @pytest.mark.asyncio
    async def test_get_build_logs_caching(self, provider, temp_dir):
        """Test that logs are cached properly"""
        session_id = "cache-test-session"

        # Add temp_dir to tracked builds
        provider._tracked_builds = [str(temp_dir)]

        # Create a mock log file
        log_file = temp_dir / f".launch-{session_id}.log"
        log_file.write_text("[INFO] Original log content\n")

        # First call - should read from file
        logs1 = await provider.get_build_logs(session_id)
        assert logs1[0] == "[INFO] Original log content"

        # Modify the log file
        log_file.write_text("[INFO] Modified log content\n")

        # Second call - should get cached version (within TTL)
        logs2 = await provider.get_build_logs(session_id)
        assert logs2[0] == "[INFO] Original log content"

        # Clear cache
        cache_key = f"logs:{session_id}"
        if cache_key in provider._cache:
            del provider._cache[cache_key]
            del provider._cache_ttl[cache_key]

        # Third call - should read new content from file
        logs3 = await provider.get_build_logs(session_id)
        assert logs3[0] == "[INFO] Modified log content"

    @pytest.mark.asyncio
    async def test_get_build_logs_handles_read_errors(self, provider, temp_dir):
        """Test that read errors are handled gracefully"""
        session_id = "error-session"

        # Add temp_dir to tracked builds
        provider._tracked_builds = [str(temp_dir)]

        # Create a log file
        log_file = temp_dir / f".launch-{session_id}.log"
        log_file.write_text("[INFO] Test log\n")

        # Make file unreadable (this might not work on all systems)
        try:
            log_file.chmod(0o000)

            # Try to read logs
            logs = await provider.get_build_logs(session_id)

            # Should either get an error message or fallback message
            assert len(logs) > 0
            # The implementation should handle the error gracefully

        finally:
            # Restore permissions and cleanup
            try:
                log_file.chmod(0o644)
            except:
                pass

    @pytest.mark.asyncio
    async def test_get_build_logs_strips_whitespace(self, provider, temp_dir):
        """Test that trailing whitespace is stripped from log lines"""
        session_id = "whitespace-session"

        # Add temp_dir to tracked builds
        provider._tracked_builds = [str(temp_dir)]

        # Create log with trailing whitespace
        log_file = temp_dir / f".launch-{session_id}.log"
        log_file.write_text("[INFO] Line with spaces    \n[INFO] Line with tabs\t\t\n")

        logs = await provider.get_build_logs(session_id)

        # Verify whitespace is stripped
        assert logs[0] == "[INFO] Line with spaces"
        assert logs[1] == "[INFO] Line with tabs"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
