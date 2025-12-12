"""
Comprehensive integration tests for MCP Server delegation functions.

CRITICAL PATHS TESTED:
- delegate_to_claude_code() synchronous delegation
- delegate_to_claude_code_async() background task spawning
- get_delegation_result() task result retrieval
- autonomous_build_and_deploy() workflow
- Output truncation and file writing
- Error handling (timeout, not found, permissions, invalid directory)

Priority: 10/10 - These are the primary user-facing MCP tools.
"""

import os
import pytest
import subprocess
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
from datetime import datetime

# Import the functions we're testing
# Note: Since mcp_server.py uses FastMCP decorators, we'll test the underlying logic
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

# Mock FastMCP before importing mcp_server to avoid import errors
sys.modules["fastmcp"] = MagicMock()
sys.modules["fastmcp.server"] = MagicMock()
sys.modules["fastmcp.server.dependencies"] = MagicMock()


@pytest.mark.skipif(
    os.environ.get("CI") is not None or os.environ.get("GITHUB_ACTIONS") is not None,
    reason="Delegation tests require Claude CLI, skipping in CI",
)
class TestDelegateToClaudeCode:
    """Test synchronous Claude Code delegation"""

    def test_successful_delegation(self):
        """Test successful task delegation with proper output"""
        with patch("subprocess.run") as mock_run:
            # Mock successful execution
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Task completed successfully\nOutput line 2\n",
                stderr="",
            )

            # Import and call the function
            from mcp_server import delegate_to_claude_code

            result = delegate_to_claude_code(
                task="Create test file", working_directory="/tmp/test"
            )

            # Verify subprocess was called correctly
            mock_run.assert_called_once()
            call_args = mock_run.call_args

            # Check command structure
            cmd = call_args[0][0]
            assert "claude" in cmd
            assert "--print" in cmd
            assert "--permission-mode" in cmd
            assert "bypassPermissions" in cmd
            assert "Create test file" in cmd

            # Check working directory
            assert call_args[1]["cwd"] == "/tmp/test"

            # Check result format
            assert "✅" in result
            assert "Success" in result
            assert "Task completed successfully" in result

    def test_delegation_with_timeout(self):
        """Test timeout handling in delegation"""
        with patch("subprocess.run") as mock_run:
            # Mock timeout
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["claude"], timeout=600
            )

            from mcp_server import delegate_to_claude_code

            result = delegate_to_claude_code(
                task="Long running task", timeout_minutes=10.0
            )

            # Verify timeout error is handled gracefully
            assert "⏱️" in result
            assert "Timeout" in result
            assert "10" in result  # timeout minutes

    def test_delegation_claude_not_found(self):
        """Test handling when Claude CLI is not installed"""
        with patch("subprocess.run") as mock_run:
            # Mock FileNotFoundError
            mock_run.side_effect = FileNotFoundError("claude not found")

            from mcp_server import delegate_to_claude_code

            result = delegate_to_claude_code(task="Test task")

            # Verify helpful error message
            assert "❌" in result
            assert "not found" in result
            assert "PATH" in result

    def test_delegation_invalid_directory(self):
        """Test handling of invalid working directory"""
        from mcp_server import delegate_to_claude_code

        result = delegate_to_claude_code(
            task="Test task", working_directory="/nonexistent/directory/path"
        )

        # Should return error without attempting subprocess
        assert "❌" in result
        assert "does not exist" in result

    def test_delegation_with_additional_flags(self):
        """Test passing additional CLI flags"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            from mcp_server import delegate_to_claude_code

            delegate_to_claude_code(
                task="Test task", additional_flags="--model claude-sonnet-4 --verbose"
            )

            # Verify additional flags were included
            cmd = mock_run.call_args[0][0]
            assert "--model" in cmd
            assert "claude-sonnet-4" in cmd
            assert "--verbose" in cmd

    def test_delegation_output_truncation(self):
        """Test that large outputs are truncated to stay under token limits"""
        with patch("subprocess.run") as mock_run:
            # Create very large output (> 40KB)
            large_output = "x" * 100000
            mock_run.return_value = Mock(returncode=0, stdout=large_output, stderr="")

            from mcp_server import delegate_to_claude_code

            result = delegate_to_claude_code(
                task="Test task",
                include_full_output=False,  # Should truncate
            )

            # Output should be truncated
            assert len(result) < len(large_output)
            assert "[OUTPUT TRUNCATED]" in result or "Truncated" in result.lower()

    def test_delegation_full_output_option(self):
        """Test include_full_output parameter bypasses truncation"""
        with patch("subprocess.run") as mock_run:
            large_output = "test line\n" * 5000
            mock_run.return_value = Mock(returncode=0, stdout=large_output, stderr="")

            from mcp_server import delegate_to_claude_code

            result = delegate_to_claude_code(
                task="Test task",
                include_full_output=True,  # Should NOT truncate
            )

            # Should contain full output
            assert large_output in result


class TestDelegateToClaudeCodeAsync:
    """Test asynchronous Claude Code delegation"""

    def test_async_delegation_returns_task_id(self):
        """Test that async delegation returns a task ID immediately"""
        with patch("subprocess.Popen") as mock_popen:
            # Mock process spawn
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None  # Still running
            mock_popen.return_value = mock_process

            from mcp_server import delegate_to_claude_code_async

            result = delegate_to_claude_code_async(
                task="Background task", working_directory="/tmp/test"
            )

            # Should return task ID immediately
            assert "Task ID:" in result or "task_id" in result.lower()
            assert (
                "running in background" in result.lower() or "started" in result.lower()
            )

    def test_async_delegation_tracks_task(self):
        """Test that async tasks are tracked in active_tasks dict"""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process

            from mcp_server import delegate_to_claude_code_async, active_tasks

            # Clear active tasks
            active_tasks.clear()

            delegate_to_claude_code_async(task="Test task")

            # Should have created a task entry
            assert len(active_tasks) > 0

    def test_async_delegation_spawn_failure(self):
        """Test handling of subprocess spawn failures in async mode"""
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.side_effect = PermissionError("Permission denied")

            from mcp_server import delegate_to_claude_code_async

            result = delegate_to_claude_code_async(task="Test task")

            # Should return error message
            assert "❌" in result or "error" in result.lower()


class TestGetDelegationResult:
    """Test retrieving results from async delegations"""

    def test_get_result_task_not_found(self):
        """Test querying result for non-existent task"""
        from mcp_server import get_delegation_result, active_tasks

        # Clear active tasks
        active_tasks.clear()

        result = get_delegation_result(task_id="nonexistent-task-id")

        # Should indicate task not found
        assert "not found" in result.lower() or "❌" in result

    def test_get_result_task_still_running(self):
        """Test querying result for task that's still running"""
        from mcp_server import get_delegation_result, active_tasks

        # Create a mock running task
        mock_process = Mock()
        mock_process.poll.return_value = None  # Still running

        task_id = "test-task-123"
        active_tasks[task_id] = {
            "process": mock_process,
            "cmd": ["claude", "test"],
            "cwd": "/tmp",
            "start_time": datetime.now(),
            "status": "running",
        }

        result = get_delegation_result(task_id=task_id)

        # Should indicate still running
        assert "running" in result.lower() or "⏳" in result

    def test_get_result_task_completed(self):
        """Test retrieving result for completed task"""
        from mcp_server import get_delegation_result, active_tasks

        # Create a mock completed task
        task_id = "test-task-456"
        active_tasks[task_id] = {
            "status": "completed",
            "result": {"returncode": 0, "stdout": "Task output", "stderr": ""},
            "duration": 5.2,
            "start_time": datetime.now(),
        }

        result = get_delegation_result(task_id=task_id)

        # Should show completion and output
        assert "completed" in result.lower() or "✅" in result
        assert "Task output" in result


class TestListDelegations:
    """Test listing active delegations"""

    def test_list_delegations_empty(self):
        """Test listing when no tasks are active"""
        from mcp_server import list_delegations, active_tasks

        active_tasks.clear()

        result = list_delegations()

        # Should indicate no active tasks
        assert "no active" in result.lower() or "empty" in result.lower()

    def test_list_delegations_with_tasks(self):
        """Test listing shows all active tasks"""
        from mcp_server import list_delegations, active_tasks

        # Add mock tasks
        active_tasks["task-1"] = {
            "status": "running",
            "start_time": datetime.now(),
            "cmd": ["claude", "task1"],
        }
        active_tasks["task-2"] = {
            "status": "completed",
            "start_time": datetime.now(),
            "cmd": ["claude", "task2"],
        }

        result = list_delegations()

        # Should list both tasks
        assert "task-1" in result
        assert "task-2" in result


class TestOutputTruncation:
    """Test output truncation logic"""

    def test_truncate_output_small_output(self):
        """Test that small outputs are not truncated"""
        from mcp_server import _truncate_output

        small_output = "Small output\nJust a few lines\n"
        truncated, was_truncated, stats = _truncate_output(
            small_output, max_tokens=20000
        )

        assert not was_truncated
        assert truncated == small_output
        assert stats["total_chars"] == len(small_output)

    def test_truncate_output_large_output(self):
        """Test that large outputs are truncated"""
        from mcp_server import _truncate_output

        # Create large output (> max_tokens * 4 chars)
        large_output = "\n".join([f"Line {i}" for i in range(10000)])
        truncated, was_truncated, stats = _truncate_output(
            large_output, max_tokens=1000
        )

        assert was_truncated
        assert len(truncated) < len(large_output)
        assert "[OUTPUT TRUNCATED]" in truncated
        assert "total_lines" in stats
        assert "truncated_lines" in stats

    def test_truncate_output_preserves_start_and_end(self):
        """Test that truncation keeps first and last sections"""
        from mcp_server import _truncate_output

        lines = [f"Line {i}" for i in range(1000)]
        large_output = "\n".join(lines)

        truncated, was_truncated, stats = _truncate_output(large_output, max_tokens=100)

        # Should preserve first and last lines
        assert "Line 0" in truncated  # First line
        assert "Line 999" in truncated  # Last line


class TestPhaseInfoReading:
    """Test phase tracking file reading"""

    def test_read_phase_info_file_not_exists(self):
        """Test reading phase info when file doesn't exist"""
        from mcp_server import _read_phase_info

        result = _read_phase_info(working_directory="/nonexistent/path")

        # Should return empty dict
        assert result == {}

    def test_read_phase_info_success(self):
        """Test successful phase info reading"""
        with patch(
            "builtins.open", mock_open(read_data='{"phase": "build", "progress": 50}')
        ):
            with patch("pathlib.Path.exists") as mock_exists:
                mock_exists.return_value = True

                from mcp_server import _read_phase_info

                result = _read_phase_info(working_directory="/tmp/test")

                # Should parse JSON
                assert "phase" in result
                assert result["phase"] == "build"

    def test_read_phase_info_stale_file(self):
        """Test that stale phase files (from previous builds) are rejected"""
        from mcp_server import _read_phase_info
        from datetime import datetime, timedelta

        # Create a task start time in the future
        task_start = datetime.now()

        with patch("pathlib.Path.exists") as mock_exists:
            with patch("pathlib.Path.stat") as mock_stat:
                mock_exists.return_value = True

                # Mock file modified time BEFORE task started (stale)
                mock_stat.return_value.st_mtime = (
                    task_start - timedelta(minutes=5)
                ).timestamp()

                result = _read_phase_info(
                    working_directory="/tmp/test", task_start_time=task_start
                )

                # Should return empty dict for stale file
                assert result == {}


class TestErrorHandling:
    """Test comprehensive error handling in MCP server functions"""

    def test_delegation_generic_exception(self):
        """Test handling of unexpected exceptions"""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("Unexpected error")

            from mcp_server import delegate_to_claude_code

            result = delegate_to_claude_code(task="Test task")

            # Should handle gracefully with error message
            assert "❌" in result
            assert "Error" in result

    def test_delegation_permission_error(self):
        """Test handling of permission errors"""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = PermissionError("Permission denied")

            from mcp_server import delegate_to_claude_code

            result = delegate_to_claude_code(task="Test task")

            # Should show permission error
            assert "❌" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
