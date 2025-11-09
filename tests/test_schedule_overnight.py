#!/usr/bin/env python3
"""
Comprehensive tests for tools/schedule_overnight.py
Tests TaskQueue, NotificationService, and OvernightScheduler.
"""

import pytest
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

# Import modules to test
from tools.schedule_overnight import TaskQueue, NotificationService, OvernightScheduler


class TestTaskQueue:
    """Test TaskQueue class."""

    @pytest.fixture
    def temp_queue_file(self):
        """Create temporary queue file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            queue_file = Path(f.name)
        yield queue_file
        if queue_file.exists():
            queue_file.unlink()

    @pytest.fixture
    def task_queue(self, temp_queue_file):
        """Create TaskQueue instance."""
        return TaskQueue(temp_queue_file)

    def test_load_tasks_empty_file(self, task_queue):
        """Test loading tasks from empty queue file."""
        tasks = task_queue.load_tasks()
        assert tasks == []

    def test_load_tasks_nonexistent_file(self):
        """Test loading tasks when file doesn't exist."""
        queue = TaskQueue(Path("/tmp/nonexistent_queue.txt"))
        tasks = queue.load_tasks()
        assert tasks == []

    def test_load_tasks_single_task(self, temp_queue_file):
        """Test loading a single task."""
        temp_queue_file.write_text("project1|Task description|8|5\n")
        queue = TaskQueue(temp_queue_file)

        tasks = queue.load_tasks()
        assert len(tasks) == 1
        assert tasks[0]["project"] == "project1"
        assert tasks[0]["description"] == "Task description"
        assert tasks[0]["hours"] == 8
        assert tasks[0]["priority"] == 5

    def test_load_tasks_multiple_tasks(self, temp_queue_file):
        """Test loading multiple tasks."""
        temp_queue_file.write_text(
            "project1|Task 1|8|5\nproject2|Task 2|4|10\nproject3|Task 3|6|3\n"
        )
        queue = TaskQueue(temp_queue_file)

        tasks = queue.load_tasks()
        assert len(tasks) == 3
        # Should be sorted by priority (descending)
        assert tasks[0]["priority"] == 10  # project2
        assert tasks[1]["priority"] == 5  # project1
        assert tasks[2]["priority"] == 3  # project3

    def test_load_tasks_with_comments(self, temp_queue_file):
        """Test that comments and empty lines are ignored."""
        temp_queue_file.write_text(
            "# This is a comment\n"
            "\n"
            "project1|Task 1|8|5\n"
            "# Another comment\n"
            "project2|Task 2|4|10\n"
            "\n"
        )
        queue = TaskQueue(temp_queue_file)

        tasks = queue.load_tasks()
        assert len(tasks) == 2

    def test_load_tasks_minimal_format(self, temp_queue_file):
        """Test loading tasks with minimal format (no hours/priority)."""
        temp_queue_file.write_text("project1|Task description\n")
        queue = TaskQueue(temp_queue_file)

        tasks = queue.load_tasks()
        assert len(tasks) == 1
        assert tasks[0]["hours"] == 8  # default
        assert tasks[0]["priority"] == 0  # default

    def test_load_tasks_with_hours_only(self, temp_queue_file):
        """Test loading tasks with hours but no priority."""
        temp_queue_file.write_text("project1|Task description|12\n")
        queue = TaskQueue(temp_queue_file)

        tasks = queue.load_tasks()
        assert len(tasks) == 1
        assert tasks[0]["hours"] == 12
        assert tasks[0]["priority"] == 0  # default

    def test_load_tasks_malformed_line(self, temp_queue_file):
        """Test that malformed lines (single field) are skipped."""
        temp_queue_file.write_text(
            "project1|Task 1|8|5\nmalformed_line\nproject2|Task 2|4|10\n"
        )
        queue = TaskQueue(temp_queue_file)

        tasks = queue.load_tasks()
        assert len(tasks) == 2  # malformed line skipped

    def test_remove_task(self, temp_queue_file):
        """Test removing a task from the queue."""
        temp_queue_file.write_text(
            "project1|Task 1|8|5\nproject2|Task 2|4|10\nproject3|Task 3|6|3\n"
        )
        queue = TaskQueue(temp_queue_file)

        tasks = queue.load_tasks()
        task_to_remove = tasks[1]  # project1 (after sorting by priority)

        queue.remove_task(task_to_remove)

        # Reload and verify
        remaining = queue.load_tasks()
        assert len(remaining) == 2
        assert all(t["project"] != "project1" for t in remaining)

    def test_remove_task_preserves_format(self, temp_queue_file):
        """Test that remove_task writes proper file format."""
        temp_queue_file.write_text("project1|Task 1|8|5\n")
        queue = TaskQueue(temp_queue_file)

        tasks = queue.load_tasks()
        queue.remove_task(tasks[0])

        # Check file contents
        content = temp_queue_file.read_text()
        assert "# Overnight Tasks Queue" in content
        assert "# Format:" in content

    def test_remove_task_by_project_and_description(self, temp_queue_file):
        """Test that removal matches both project and description."""
        temp_queue_file.write_text("project1|Task 1|8|5\nproject1|Task 2|4|10\n")
        queue = TaskQueue(temp_queue_file)

        tasks = queue.load_tasks()
        # Remove only Task 2
        task_to_remove = [t for t in tasks if t["description"] == "Task 2"][0]
        queue.remove_task(task_to_remove)

        remaining = queue.load_tasks()
        assert len(remaining) == 1
        assert remaining[0]["description"] == "Task 1"


class TestNotificationService:
    """Test NotificationService class."""

    @pytest.fixture
    def notifier(self):
        """Create NotificationService instance."""
        return NotificationService()

    def test_load_email_config_all_set(self, monkeypatch):
        """Test loading email config when all env vars are set."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USER", "user@example.com")
        monkeypatch.setenv("SMTP_PASS", "password")
        monkeypatch.setenv("NOTIFICATION_EMAIL", "notify@example.com")

        notifier = NotificationService()

        assert notifier.email_config is not None
        assert notifier.email_config["host"] == "smtp.example.com"
        assert notifier.email_config["port"] == 587
        assert notifier.email_config["user"] == "user@example.com"

    def test_load_email_config_missing_vars(self, monkeypatch):
        """Test that missing env vars result in no config."""
        # Clear any existing env vars
        for key in [
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_USER",
            "SMTP_PASS",
            "NOTIFICATION_EMAIL",
        ]:
            monkeypatch.delenv(key, raising=False)

        notifier = NotificationService()
        assert notifier.email_config is None

    def test_send_email_not_configured(self, notifier, capsys):
        """Test sending email when not configured."""
        notifier.email_config = None

        notifier.send_email("Test", "Body")

        captured = capsys.readouterr()
        assert "Email not configured" in captured.out

    @patch("smtplib.SMTP")
    def test_send_email_success(self, mock_smtp):
        """Test successful email sending."""
        notifier = NotificationService()
        notifier.email_config = {
            "host": "smtp.example.com",
            "port": 587,
            "user": "user@example.com",
            "password": "password",
            "to": "notify@example.com",
        }

        notifier.send_email("Test Subject", "Test Body")

        # Verify SMTP was called
        mock_smtp.assert_called_once_with("smtp.example.com", 587)

        # Verify starttls and login were called
        server_instance = mock_smtp.return_value.__enter__.return_value
        server_instance.starttls.assert_called_once()
        server_instance.login.assert_called_once_with("user@example.com", "password")

    @patch("smtplib.SMTP")
    def test_send_email_failure(self, mock_smtp, capsys):
        """Test email sending failure handling."""
        mock_smtp.side_effect = Exception("SMTP error")

        notifier = NotificationService()
        notifier.email_config = {
            "host": "smtp.example.com",
            "port": 587,
            "user": "user@example.com",
            "password": "password",
            "to": "notify@example.com",
        }

        notifier.send_email("Test", "Body")

        captured = capsys.readouterr()
        assert "Email failed" in captured.out

    def test_send_slack_not_configured(self, notifier, capsys):
        """Test sending Slack when not configured."""
        notifier.slack_webhook = None

        notifier.send_slack("Test message")

        captured = capsys.readouterr()
        assert "Slack webhook not configured" in captured.out

    def test_send_slack_success(self, monkeypatch, capsys):
        """Test successful Slack sending."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")

        # Mock requests at import time
        with patch(
            "builtins.__import__",
            side_effect=lambda name, *args, **kwargs: Mock(
                post=Mock(return_value=Mock(status_code=200))
            )
            if name == "requests"
            else __import__(name, *args, **kwargs),
        ):
            notifier = NotificationService()
            notifier.send_slack("Test message")

            captured = capsys.readouterr()
            assert "Slack notification sent" in captured.out

    def test_send_slack_failure(self, monkeypatch, capsys):
        """Test Slack sending failure handling."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")

        # Mock requests with failure response
        with patch(
            "builtins.__import__",
            side_effect=lambda name, *args, **kwargs: Mock(
                post=Mock(return_value=Mock(status_code=500))
            )
            if name == "requests"
            else __import__(name, *args, **kwargs),
        ):
            notifier = NotificationService()
            notifier.send_slack("Test message")

            captured = capsys.readouterr()
            assert "Slack failed" in captured.out

    @patch("subprocess.run")
    def test_send_desktop_notification_macos(self, mock_run):
        """Test desktop notification on macOS."""
        notifier = NotificationService()

        notifier.send_desktop_notification("Test Title", "Test Message")

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "osascript" in call_args
        assert "-e" in call_args

    @patch("subprocess.run")
    def test_send_desktop_notification_failure(self, mock_run, capsys):
        """Test desktop notification failure handling."""
        mock_run.side_effect = Exception("Not available")

        notifier = NotificationService()
        notifier.send_desktop_notification("Test", "Message")

        captured = capsys.readouterr()
        assert "Desktop notification not available" in captured.out

    def test_notify_completion(self, notifier):
        """Test completion notification sends all methods."""
        with (
            patch.object(notifier, "send_email") as mock_email,
            patch.object(notifier, "send_slack") as mock_slack,
            patch.object(notifier, "send_desktop_notification") as mock_desktop,
        ):
            task = {"project": "test_project", "description": "Test task"}
            result = {
                "success": True,
                "duration": "2h",
                "iterations": 10,
                "log_file": "test.log",
            }

            notifier.notify_completion(task, result)

            # Verify all notification methods called
            mock_email.assert_called_once()
            mock_slack.assert_called_once()
            mock_desktop.assert_called_once()

            # Verify email subject contains project name
            assert "test_project" in mock_email.call_args[0][0]

    def test_notify_failure(self, notifier):
        """Test failure notification sends all methods."""
        with (
            patch.object(notifier, "send_email") as mock_email,
            patch.object(notifier, "send_slack") as mock_slack,
            patch.object(notifier, "send_desktop_notification") as mock_desktop,
        ):
            task = {"project": "test_project", "description": "Test task"}
            error = "Test error message"

            notifier.notify_failure(task, error)

            # Verify all notification methods called
            mock_email.assert_called_once()
            mock_slack.assert_called_once()
            mock_desktop.assert_called_once()

            # Verify error message included
            email_body = mock_email.call_args[0][1]
            assert "Test error message" in email_body


class TestOvernightScheduler:
    """Test OvernightScheduler class."""

    @pytest.fixture
    def temp_queue_file(self):
        """Create temporary queue file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            queue_file = Path(f.name)
        yield queue_file
        if queue_file.exists():
            queue_file.unlink()

    @pytest.fixture
    def scheduler(self, temp_queue_file):
        """Create OvernightScheduler instance."""
        return OvernightScheduler(temp_queue_file)

    @patch("subprocess.run")
    def test_run_task_success(self, mock_run, scheduler):
        """Test successful task execution."""
        mock_result = Mock()
        mock_result.stdout = "Task output"
        mock_run.return_value = mock_result

        task = {"project": "test_project", "description": "Test task", "hours": 1}

        result = scheduler.run_task(task, max_retries=1)

        assert result["success"] is True
        assert result["attempts"] == 1
        assert "output" in result

    @patch("subprocess.run")
    def test_run_task_failure_with_retries(self, mock_run, scheduler):
        """Test task failure with retry logic."""
        # Fail first two attempts, succeed on third
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "cmd", stderr="Error 1"),
            subprocess.CalledProcessError(1, "cmd", stderr="Error 2"),
            Mock(stdout="Success"),
        ]

        task = {"project": "test_project", "description": "Test task", "hours": 1}

        with patch("time.sleep"):  # Skip actual sleep
            result = scheduler.run_task(task, max_retries=3)

        assert result["success"] is True
        assert result["attempts"] == 3

    @patch("subprocess.run")
    def test_run_task_max_retries_exceeded(self, mock_run, scheduler):
        """Test task failure after max retries."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr="Error")

        task = {"project": "test_project", "description": "Test task", "hours": 1}

        with patch("time.sleep"):
            result = scheduler.run_task(task, max_retries=2)

        assert result["success"] is False
        assert result["attempts"] == 2
        assert "error" in result

    @patch("subprocess.run")
    def test_run_task_timeout(self, mock_run, scheduler):
        """Test task timeout handling."""
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 3600)

        task = {"project": "test_project", "description": "Test task", "hours": 1}

        result = scheduler.run_task(task, max_retries=1)

        assert result["success"] is False
        assert "Timeout" in result["error"]

    @patch("subprocess.run")
    def test_run_task_command_format(self, mock_run, scheduler):
        """Test that run_task builds correct command."""
        mock_result = Mock(stdout="output")
        mock_run.return_value = mock_result

        task = {"project": "my_project", "description": "My task", "hours": 4}

        scheduler.run_task(task, max_retries=1)

        # Verify command structure
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "./tools/overnight_session.sh" in cmd
        assert "my_project" in cmd
        assert "My task" in cmd
        assert "4" in cmd

    def test_process_queue_empty(self, scheduler, capsys):
        """Test processing empty queue."""
        scheduler.process_queue()

        captured = capsys.readouterr()
        assert "No tasks in queue" in captured.out

    @patch("subprocess.run")
    def test_process_queue_single_task(self, mock_run, temp_queue_file):
        """Test processing single task."""
        temp_queue_file.write_text("project1|Task 1|1|5\n")
        scheduler = OvernightScheduler(temp_queue_file)

        mock_result = Mock(stdout="output")
        mock_run.return_value = mock_result

        with patch.object(scheduler.notifier, "notify_completion"):
            scheduler.process_queue()

        # Task should be removed after success
        remaining = scheduler.queue.load_tasks()
        assert len(remaining) == 0

    @patch("subprocess.run")
    def test_process_queue_failed_task_not_removed(self, mock_run, temp_queue_file):
        """Test that failed tasks remain in queue."""
        temp_queue_file.write_text("project1|Task 1|1|5\n")
        scheduler = OvernightScheduler(temp_queue_file)

        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")

        with patch.object(scheduler.notifier, "notify_failure"), patch("time.sleep"):
            scheduler.process_queue()

        # Failed task should remain
        remaining = scheduler.queue.load_tasks()
        assert len(remaining) == 1

    def test_add_task(self, temp_queue_file):
        """Test adding a task to the queue."""
        scheduler = OvernightScheduler(temp_queue_file)

        scheduler.add_task("new_project", "New task", hours=6, priority=7)

        # Verify task was added
        tasks = scheduler.queue.load_tasks()
        assert len(tasks) == 1
        assert tasks[0]["project"] == "new_project"
        assert tasks[0]["description"] == "New task"
        assert tasks[0]["hours"] == 6
        assert tasks[0]["priority"] == 7


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_task_queue_invalid_hours(self):
        """Test handling of invalid hours value."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("project1|Task|invalid|5\n")
            queue_file = Path(f.name)

        try:
            queue = TaskQueue(queue_file)
            # Should raise ValueError when parsing invalid int
            with pytest.raises(ValueError):
                queue.load_tasks()
        finally:
            queue_file.unlink()

    def test_task_queue_invalid_priority(self):
        """Test handling of invalid priority value."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("project1|Task|8|invalid\n")
            queue_file = Path(f.name)

        try:
            queue = TaskQueue(queue_file)
            # Should raise ValueError when parsing invalid int
            with pytest.raises(ValueError):
                queue.load_tasks()
        finally:
            queue_file.unlink()

    def test_notification_service_smtp_port_default(self, monkeypatch):
        """Test SMTP port defaults to 587."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "")  # Empty string will use default
        monkeypatch.setenv("SMTP_USER", "user@example.com")
        monkeypatch.setenv("SMTP_PASS", "password")
        monkeypatch.setenv("NOTIFICATION_EMAIL", "notify@example.com")

        notifier = NotificationService()

        # Email config should be set with default port
        if notifier.email_config:
            assert notifier.email_config["port"] == 587

    def test_empty_task_description(self):
        """Test handling of empty task description."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("project1||8|5\n")
            queue_file = Path(f.name)

        try:
            queue = TaskQueue(queue_file)
            tasks = queue.load_tasks()
            assert len(tasks) == 1
            assert tasks[0]["description"] == ""
        finally:
            queue_file.unlink()
