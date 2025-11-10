#!/usr/bin/env python3
"""
Tests for MCP Server helper functions.

Coverage target: 90%+ for helper functions
Priority: 8/10 - Utility functions used by core MCP tools

HELPER FUNCTIONS TESTED:
- _get_context_foundry_parent_dir() - Get CF installation parent directory
- _write_delegation_metadata() - Write task metadata to disk
- _write_full_output_to_file() - Save build output to file
- _create_output_summary() - Create smart output summary
"""

import pytest
import json
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path


# Mock FastMCP with pass-through decorators
class MockFastMCP:
    def __init__(self, *args, **kwargs):
        pass

    def tool(self, *args, **kwargs):
        """Decorator that returns the original function unchanged"""

        def decorator(func):
            return func

        return decorator if not args or callable(args[0]) else decorator

    def resource(self, *args, **kwargs):
        """Decorator that returns the original function unchanged"""

        def decorator(func):
            return func

        return decorator


mock_module = MagicMock()
mock_module.FastMCP = MockFastMCP
mock_module.Context = MagicMock

sys.modules["fastmcp"] = mock_module
sys.modules["fastmcp.server"] = MagicMock()
sys.modules["fastmcp.server.dependencies"] = MagicMock()
sys.modules["fastmcp.server.dependencies"].get_context = MagicMock()

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

# Import after mocking
from mcp_server import (  # noqa: E402
    _create_output_summary,
    _get_context_foundry_parent_dir,
    _write_delegation_metadata,
    _write_full_output_to_file,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    """Create temporary home directory for metadata storage"""
    temp_home_dir = tmp_path / "home"
    temp_home_dir.mkdir()
    monkeypatch.setenv("HOME", str(temp_home_dir))
    return temp_home_dir


@pytest.fixture
def temp_working_dir(tmp_path):
    """Create temporary working directory"""
    working_dir = tmp_path / "project"
    working_dir.mkdir()
    return working_dir


# ============================================================================
# Tests for _get_context_foundry_parent_dir()
# ============================================================================


class TestGetContextFoundryParentDir:
    """Tests for _get_context_foundry_parent_dir() function"""

    def test_get_parent_dir_returns_correct_path(self):
        """Test that function returns correct parent directory"""
        result = _get_context_foundry_parent_dir()

        # Result should be a Path object
        assert isinstance(result, Path)

        # Result should be absolute
        assert result.is_absolute()

        # Result should be parent of context-foundry directory
        # Expected structure: /some/path/context-foundry/tools/mcp_server.py
        # Parent of context-foundry is /some/path
        assert result.exists()

    def test_get_parent_dir_is_absolute(self):
        """Test that returned path is absolute"""
        result = _get_context_foundry_parent_dir()
        assert result.is_absolute()

    def test_get_parent_dir_is_directory(self):
        """Test that returned path is a directory"""
        result = _get_context_foundry_parent_dir()
        assert result.is_dir()


# ============================================================================
# Tests for _write_delegation_metadata()
# ============================================================================


class TestWriteDelegationMetadata:
    """Tests for _write_delegation_metadata() function"""

    def test_write_metadata_creates_directory(self, temp_home):
        """Test that function creates delegations directory if missing"""
        task_id = "test-task-123"
        metadata = {"status": "running", "start_time": "2025-01-13T00:00:00Z"}

        _write_delegation_metadata(task_id, metadata)

        # Check that directory was created
        delegations_dir = temp_home / ".context-foundry" / "delegations"
        assert delegations_dir.exists()
        assert delegations_dir.is_dir()

    def test_write_metadata_success(self, temp_home):
        """Test successful metadata write"""
        task_id = "test-task-456"
        metadata = {
            "status": "completed",
            "start_time": "2025-01-13T00:00:00Z",
            "working_directory": "/tmp/test",
        }

        _write_delegation_metadata(task_id, metadata)

        # Check that file was created with correct content
        task_file = (
            temp_home / ".context-foundry" / "delegations" / f"task-{task_id}.json"
        )
        assert task_file.exists()

        # Read and verify content
        content = json.loads(task_file.read_text())
        assert content == metadata
        assert content["status"] == "completed"

    def test_write_metadata_permission_error(self, temp_home, capsys):
        """Test graceful handling of permission errors"""
        task_id = "test-task-789"
        metadata = {"status": "running"}

        # Create directory but make it non-writable
        delegations_dir = temp_home / ".context-foundry" / "delegations"
        delegations_dir.mkdir(parents=True, exist_ok=True)

        with patch(
            "pathlib.Path.write_text", side_effect=PermissionError("Access denied")
        ):
            # Should not raise exception, just print warning
            _write_delegation_metadata(task_id, metadata)

            # Check that warning was printed to stderr
            captured = capsys.readouterr()
            assert "Warning: Failed to write delegation metadata" in captured.err

    def test_write_metadata_invalid_json(self, temp_home, capsys):
        """Test handling of non-serializable objects"""
        task_id = "test-task-abc"
        # Create metadata with non-serializable object
        metadata = {"status": "running", "func": lambda x: x}

        with patch("json.dumps", side_effect=TypeError("Object not JSON serializable")):
            # Should not crash, just print warning
            _write_delegation_metadata(task_id, metadata)

            captured = capsys.readouterr()
            assert "Warning: Failed to write delegation metadata" in captured.err

    def test_write_metadata_disk_full(self, temp_home, capsys):
        """Test handling of disk full errors"""
        task_id = "test-task-def"
        metadata = {"status": "running"}

        with patch(
            "pathlib.Path.write_text", side_effect=OSError("No space left on device")
        ):
            # Should handle gracefully
            _write_delegation_metadata(task_id, metadata)

            captured = capsys.readouterr()
            assert "Warning: Failed to write delegation metadata" in captured.err


# ============================================================================
# Tests for _write_full_output_to_file()
# ============================================================================


class TestWriteFullOutputToFile:
    """Tests for _write_full_output_to_file() function"""

    def test_write_output_creates_context_dir(self, temp_working_dir):
        """Test that function creates .context-foundry directory"""
        stdout = "Build successful"
        stderr = ""
        task_id = "build-123"

        result = _write_full_output_to_file(
            str(temp_working_dir), stdout, stderr, task_id
        )

        # Check directory was created
        context_dir = temp_working_dir / ".context-foundry"
        assert context_dir.exists()
        assert context_dir.is_dir()

        # Check result is a valid path
        assert "build-output-build-123.txt" in result

    def test_write_output_success(self, temp_working_dir):
        """Test successful output write with valid stdout/stderr"""
        stdout = "Line 1\nLine 2\nLine 3"
        stderr = "Warning: Something happened"
        task_id = "build-456"

        _write_full_output_to_file(str(temp_working_dir), stdout, stderr, task_id)

        # Check file was created
        output_file = (
            temp_working_dir / ".context-foundry" / f"build-output-{task_id}.txt"
        )
        assert output_file.exists()

        # Read and verify content
        content = output_file.read_text()
        assert "STDOUT" in content
        assert "STDERR" in content
        assert "Line 1" in content
        assert "Warning: Something happened" in content
        assert "=" * 80 in content

    def test_write_output_empty_streams(self, temp_working_dir):
        """Test handling of empty stdout/stderr"""
        stdout = ""
        stderr = ""
        task_id = "build-789"

        _write_full_output_to_file(str(temp_working_dir), stdout, stderr, task_id)

        output_file = (
            temp_working_dir / ".context-foundry" / f"build-output-{task_id}.txt"
        )
        content = output_file.read_text()

        # Should write "(empty)" for empty streams
        assert "(empty)" in content

    def test_write_output_none_streams(self, temp_working_dir):
        """Test handling of None stdout/stderr"""
        stdout = None
        stderr = None
        task_id = "build-abc"

        _write_full_output_to_file(str(temp_working_dir), stdout, stderr, task_id)

        output_file = (
            temp_working_dir / ".context-foundry" / f"build-output-{task_id}.txt"
        )
        content = output_file.read_text()

        # Should write "(empty)" for None streams
        assert "(empty)" in content

    def test_write_output_permission_error(self, temp_working_dir):
        """Test that permission errors return error message instead of crashing"""
        stdout = "Test output"
        stderr = ""
        task_id = "build-def"

        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            result = _write_full_output_to_file(
                str(temp_working_dir), stdout, stderr, task_id
            )

            # Should return error message, not crash
            assert "Error writing output file" in result
            assert "Access denied" in result

    def test_write_output_formatting(self, temp_working_dir):
        """Test that output formatting is correct with separators"""
        stdout = "Standard output line"
        stderr = "Error output line"
        task_id = "build-ghi"

        _write_full_output_to_file(str(temp_working_dir), stdout, stderr, task_id)

        output_file = (
            temp_working_dir / ".context-foundry" / f"build-output-{task_id}.txt"
        )
        content = output_file.read_text()

        # Check proper formatting
        lines = content.split("\n")

        # Should have separators (80 equals signs)
        separator_lines = [line for line in lines if line == "=" * 80]
        assert len(separator_lines) == 4  # 2 for stdout section, 2 for stderr section

        # Check section headers
        assert "STDOUT" in content
        assert "STDERR" in content


# ============================================================================
# Tests for _create_output_summary()
# ============================================================================


class TestCreateOutputSummary:
    """Tests for _create_output_summary() function"""

    def test_summary_empty_output(self):
        """Test handling of empty output"""
        output = ""
        summary, stats = _create_output_summary(output)

        assert summary == "(empty)"
        assert stats["total_lines"] == 0
        assert stats["shown_lines"] == 0
        assert stats["hidden_lines"] == 0

    def test_summary_short_output(self):
        """Test that short output is returned in full"""
        # Create output with less than max_lines * 2 lines
        lines = [f"Line {i}" for i in range(50)]
        output = "\n".join(lines)

        summary, stats = _create_output_summary(output, max_lines=50)

        # Should return full output
        assert summary == output
        assert stats["total_lines"] == 50
        assert stats["shown_lines"] == 50
        assert stats["hidden_lines"] == 0

    def test_summary_long_output(self):
        """Test that long output is properly summarized"""
        # Create output with more than max_lines * 2 lines
        lines = [f"Line {i}" for i in range(200)]
        output = "\n".join(lines)

        summary, stats = _create_output_summary(output, max_lines=50)

        # Should show first 50 and last 50 lines
        assert "Line 0" in summary  # First line
        assert "Line 49" in summary  # 50th line
        assert "Line 150" in summary  # Line 200 - 50 + 1
        assert "Line 199" in summary  # Last line

        # Should indicate hidden lines
        assert "lines hidden" in summary

        # Check statistics
        assert stats["total_lines"] == 200
        assert stats["shown_lines"] == 100  # 50 from start + 50 from end
        assert stats["hidden_lines"] == 100

    def test_summary_statistics_correct(self):
        """Test that statistics are calculated correctly"""
        lines = [f"Line {i}" for i in range(150)]
        output = "\n".join(lines)

        summary, stats = _create_output_summary(output, max_lines=30)

        # Verify statistics
        assert stats["total_lines"] == 150
        assert stats["shown_lines"] == 60  # 30 from start + 30 from end
        assert stats["hidden_lines"] == 90  # 150 - 60

    def test_summary_exactly_max_lines(self):
        """Test edge case where output is exactly max_lines * 2"""
        # Exactly max_lines * 2 lines (boundary case)
        lines = [f"Line {i}" for i in range(100)]
        output = "\n".join(lines)

        summary, stats = _create_output_summary(output, max_lines=50)

        # Should return full output (not summarized)
        assert summary == output
        assert stats["total_lines"] == 100
        assert stats["shown_lines"] == 100
        assert stats["hidden_lines"] == 0

    def test_summary_custom_max_lines(self):
        """Test with different max_lines values"""
        lines = [f"Line {i}" for i in range(200)]
        output = "\n".join(lines)

        # Test with max_lines=20
        summary, stats = _create_output_summary(output, max_lines=20)

        assert stats["total_lines"] == 200
        assert stats["shown_lines"] == 40  # 20 from start + 20 from end
        assert stats["hidden_lines"] == 160

        # Verify first and last lines
        assert "Line 0" in summary
        assert "Line 19" in summary
        assert "Line 180" in summary
        assert "Line 199" in summary

    def test_summary_separator_format(self):
        """Test that separator format is correct"""
        lines = [f"Line {i}" for i in range(200)]
        output = "\n".join(lines)

        summary, stats = _create_output_summary(output, max_lines=50)

        # Check separator contains hidden line count
        assert "100 lines hidden" in summary
        assert "=" * 60 in summary
        assert "see output_file for full content" in summary

    def test_summary_none_output(self):
        """Test handling of None output"""
        output = None
        summary, stats = _create_output_summary(output)

        # Should handle None gracefully (treated as empty)
        assert summary == "(empty)"
        assert stats["total_lines"] == 0


# ============================================================================
# Coverage and Documentation Tests
# ============================================================================


class TestCoverageTargets:
    """Verify that coverage targets are documented"""

    def test_coverage_targets_documented(self):
        """Ensure this file documents its coverage targets"""
        # Read this file
        test_file = Path(__file__)
        content = test_file.read_text()

        # Check for coverage target documentation
        assert "Coverage target" in content
        assert "HELPER FUNCTIONS TESTED" in content

        # Check that all target functions are listed
        assert "_get_context_foundry_parent_dir" in content
        assert "_write_delegation_metadata" in content
        assert "_write_full_output_to_file" in content
        assert "_create_output_summary" in content
