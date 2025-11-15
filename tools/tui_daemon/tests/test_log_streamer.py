"""
Tests for LogStreamer - Real-time log polling
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock

from tools.tui_daemon.log_streamer import LogStreamer
from tools.tui_daemon.daemon_client import LogEntry


class TestLogStreamer:
    """Test suite for LogStreamer"""

    def test_init(self, mock_daemon_client):
        """Test initialization"""
        streamer = LogStreamer(mock_daemon_client, poll_interval=0.5)

        assert streamer.daemon_client == mock_daemon_client
        assert streamer.poll_interval == 0.5
        assert streamer.is_streaming is False

    def test_format_log(self):
        """Test log formatting with colors"""
        log = LogEntry(
            job_id="test",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            level="INFO",
            message="Test message",
            phase="scout",
            source="test",
        )

        formatted = LogStreamer.format_log(log)

        # Check that formatted text contains expected components
        assert "12:00:00" in str(formatted)
        assert "INFO" in str(formatted)
        assert "scout" in str(formatted)
        assert "Test message" in str(formatted)

    def test_format_log_levels(self):
        """Test formatting for different log levels"""
        for level in ["INFO", "SUCCESS", "WARNING", "ERROR", "DEBUG"]:
            log = LogEntry(
                job_id="test",
                timestamp=datetime.now(),
                level=level,
                message=f"Test {level}",
                phase=None,
                source=None,
            )

            formatted = LogStreamer.format_log(
                log, show_timestamp=False, show_phase=False
            )
            assert level in str(formatted)

    def test_format_log_without_timestamp(self):
        """Test formatting without timestamp"""
        log = LogEntry(
            job_id="test",
            timestamp=datetime.now(),
            level="INFO",
            message="Test",
            phase=None,
            source=None,
        )

        formatted = LogStreamer.format_log(log, show_timestamp=False)
        assert "[INFO]" in str(formatted)

    @pytest.mark.asyncio
    async def test_start_stop_streaming(self, mock_daemon_client):
        """Test starting and stopping log streaming"""
        streamer = LogStreamer(mock_daemon_client, poll_interval=0.1)
        callback = Mock()

        # Start streaming
        streamer.start_streaming("test-job-id", callback)
        assert streamer.is_streaming is True
        assert streamer._current_job_id == "test-job-id"

        # Give it a moment to start
        await asyncio.sleep(0.05)

        # Stop streaming
        streamer.stop_streaming()
        assert streamer.is_streaming is False
        assert streamer._current_job_id is None

    def test_get_new_logs(self, mock_daemon_client, sample_log_entries):
        """Test getting new logs"""
        mock_daemon_client.get_logs = Mock(return_value=sample_log_entries)

        streamer = LogStreamer(mock_daemon_client)
        streamer._current_job_id = "test-job"

        logs = streamer.get_new_logs()

        assert len(logs) == 4
        assert all(isinstance(log, LogEntry) for log in logs)
        mock_daemon_client.get_logs.assert_called_once_with(
            "test-job", since_timestamp=None
        )
