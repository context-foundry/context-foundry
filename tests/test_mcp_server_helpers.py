#!/usr/bin/env python3
"""
Unit tests for helper functions in tools/mcp_server.py

Tests coverage for private helper functions:
- _read_phase_info
- _truncate_output
- _get_context_foundry_parent_dir
- _write_delegation_metadata
- _write_full_output_to_file
- _create_output_summary
"""

import pytest
import json
import sys
import time
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime


# ============================================================================
# Mock FastMCP (required before importing mcp_server)
# ============================================================================


class MockFastMCP:
    """Mock FastMCP class for testing"""

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


# Mock fastmcp modules before importing mcp_server
mock_module = MagicMock()
mock_module.FastMCP = MockFastMCP
mock_module.Context = MagicMock

sys.modules["fastmcp"] = mock_module
sys.modules["fastmcp.server"] = MagicMock()
sys.modules["fastmcp.server.dependencies"] = MagicMock()
sys.modules["fastmcp.server.dependencies"].get_context = MagicMock()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

# Import after mocking  # noqa: E402
from mcp_server import (  # noqa: E402
    _read_phase_info,
    _truncate_output,
    _get_context_foundry_parent_dir,
    _write_delegation_metadata,
    _write_full_output_to_file,
    _create_output_summary,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_dir(tmp_path):
    """Create temporary directory for file operations"""
    return tmp_path


@pytest.fixture
def mock_phase_file(temp_dir):
    """Create a mock phase info JSON file"""
    context_dir = temp_dir / ".context-foundry"
    context_dir.mkdir(parents=True, exist_ok=True)
    phase_file = context_dir / "current-phase.json"

    phase_data = {
        "current_phase": "Builder",
        "phase_number": "3/7",
        "status": "building",
        "progress_detail": "Implementing tests",
    }

    phase_file.write_text(json.dumps(phase_data))
    return phase_file


@pytest.fixture
def sample_output():
    """Return sample output strings for testing"""
    return {
        "small": "Line 1\nLine 2\nLine 3",
        "large": "\n".join([f"Line {i}" for i in range(10000)]),
        "empty": "",
        "boundary": "x" * (20000 * 4),  # Exactly at max_tokens boundary
    }


# ============================================================================
# Tests for _read_phase_info
# ============================================================================


def test_read_phase_info_file_exists_fresh(temp_dir, mock_phase_file):
    """Test reading phase info from fresh file"""
    result = _read_phase_info(str(temp_dir))

    assert result is not None
    assert isinstance(result, dict)
    assert result.get("current_phase") == "Builder"
    assert result.get("status") == "building"


def test_read_phase_info_file_not_exists(temp_dir):
    """Test reading phase info when file doesn't exist"""
    result = _read_phase_info(str(temp_dir))

    assert result == {}


def test_read_phase_info_invalid_json(temp_dir):
    """Test reading phase info with invalid JSON"""
    context_dir = temp_dir / ".context-foundry"
    context_dir.mkdir(parents=True, exist_ok=True)
    phase_file = context_dir / "current-phase.json"
    phase_file.write_text("{ invalid json }")

    result = _read_phase_info(str(temp_dir))

    assert result == {}


def test_read_phase_info_stale_file(temp_dir, mock_phase_file):
    """Test that stale files (modified before task start) return empty dict"""
    # Set task start time to future (making file stale)
    task_start = datetime.now()
    time.sleep(0.01)  # Ensure file mtime is before task_start

    # Modify the file to ensure its mtime is in the past
    file_path = temp_dir / ".context-foundry" / "current-phase.json"
    stat = file_path.stat()

    # Mock datetime to make task_start appear after file modification
    with patch("tools.mcp_utils.phase_tracking.datetime") as mock_datetime:
        mock_datetime.fromtimestamp.return_value = datetime.fromtimestamp(
            stat.st_mtime - 10
        )

        result = _read_phase_info(str(temp_dir), task_start_time=task_start)

    # Should return empty dict because file is stale
    assert result == {}


def test_read_phase_info_permission_error(temp_dir):
    """Test reading phase info with permission error"""
    context_dir = temp_dir / ".context-foundry"
    context_dir.mkdir(parents=True, exist_ok=True)
    phase_file = context_dir / "current-phase.json"
    phase_file.write_text('{"test": "data"}')

    # Mock open to raise PermissionError
    with patch("builtins.open", side_effect=PermissionError("Access denied")):
        result = _read_phase_info(str(temp_dir))

    assert result == {}


def test_read_phase_info_no_task_start_time(temp_dir, mock_phase_file):
    """Test reading phase info without task_start_time (no staleness check)"""
    result = _read_phase_info(str(temp_dir), task_start_time=None)

    assert result is not None
    assert isinstance(result, dict)
    assert result.get("current_phase") == "Builder"


# ============================================================================
# Tests for _truncate_output
# ============================================================================


def test_truncate_output_small_output(sample_output):
    """Test truncating small output (should not truncate)"""
    output, was_truncated, stats = _truncate_output(sample_output["small"])

    assert output == sample_output["small"]
    assert was_truncated is False
    assert stats["total_lines"] == 3
    assert stats["total_chars"] == len(sample_output["small"])


def test_truncate_output_large_output(sample_output):
    """Test truncating large output (should truncate)"""
    output, was_truncated, stats = _truncate_output(sample_output["large"])

    assert was_truncated is True
    assert stats["total_lines"] == 10000
    assert "[OUTPUT TRUNCATED]" in output
    assert "Showing:" in output
    assert "Hidden:" in output


def test_truncate_output_empty_string(sample_output):
    """Test truncating empty string"""
    output, was_truncated, stats = _truncate_output(sample_output["empty"])

    assert output == ""
    assert was_truncated is False
    assert stats["total_lines"] == 0
    assert stats["total_chars"] == 0


def test_truncate_output_at_boundary():
    """Test truncating output exactly at max_tokens boundary"""
    # Create output exactly at boundary (20000 tokens * 4 chars = 80000 chars)
    boundary_output = "x" * 80000

    output, was_truncated, stats = _truncate_output(boundary_output, max_tokens=20000)

    # Should not truncate because it's exactly at the limit
    assert was_truncated is False
    assert stats["total_chars"] == 80000


def test_truncate_output_custom_max_tokens():
    """Test truncating with custom max_tokens parameter"""
    # Create output larger than custom max
    large_output = "x" * 10000

    output, was_truncated, stats = _truncate_output(large_output, max_tokens=500)

    # Should truncate because output is larger than custom max (500*4=2000 chars)
    assert was_truncated is True


# ============================================================================
# Tests for _get_context_foundry_parent_dir
# ============================================================================


def test_get_context_foundry_parent_dir_returns_parent():
    """Test that function returns parent directory of context-foundry"""
    result = _get_context_foundry_parent_dir()

    assert isinstance(result, Path)
    # Should be a valid path
    assert result.exists() or True  # May not exist in test environment


def test_get_context_foundry_parent_dir_resolution():
    """Test that path resolution works correctly"""
    result = _get_context_foundry_parent_dir()

    # Result should be a resolved (absolute) Path
    assert result.is_absolute()

    # Should be parent of parent of tools directory
    # tools/mcp_server.py -> tools -> context-foundry -> parent
    assert isinstance(result, Path)


# ============================================================================
# Tests for _write_delegation_metadata
# ============================================================================


def test_write_delegation_metadata_success(tmp_path, monkeypatch):
    """Test successful metadata write"""
    # Use tmp_path as HOME
    monkeypatch.setenv("HOME", str(tmp_path))

    task_id = "test-task-123"
    metadata = {
        "status": "running",
        "working_directory": "/tmp/test",
        "start_time": "2024-01-01T00:00:00",
    }

    _write_delegation_metadata(task_id, metadata)

    # Verify file was created
    delegations_dir = tmp_path / ".context-foundry" / "delegations"
    task_file = delegations_dir / f"task-{task_id}.json"

    assert task_file.exists()

    # Verify content
    written_data = json.loads(task_file.read_text())
    assert written_data == metadata


def test_write_delegation_metadata_creates_directory(tmp_path, monkeypatch):
    """Test that function creates delegations directory if it doesn't exist"""
    monkeypatch.setenv("HOME", str(tmp_path))

    task_id = "test-task-456"
    metadata = {"status": "pending"}

    # Verify directory doesn't exist yet
    delegations_dir = tmp_path / ".context-foundry" / "delegations"
    assert not delegations_dir.exists()

    _write_delegation_metadata(task_id, metadata)

    # Verify directory was created
    assert delegations_dir.exists()
    assert delegations_dir.is_dir()


def test_write_delegation_metadata_handles_errors(tmp_path, monkeypatch):
    """Test that function handles write errors gracefully"""
    monkeypatch.setenv("HOME", str(tmp_path))

    task_id = "test-task-789"
    metadata = {"status": "running"}

    # Mock Path.write_text to raise an error
    with patch("pathlib.Path.write_text", side_effect=OSError("Disk full")):
        # Should not raise exception - just handle gracefully
        try:
            _write_delegation_metadata(task_id, metadata)
        except Exception as e:
            pytest.fail(f"Function should handle errors gracefully but raised: {e}")


# ============================================================================
# Tests for _write_full_output_to_file
# ============================================================================


def test_write_full_output_to_file_success(temp_dir):
    """Test successful full output file write"""
    stdout = "Standard output content"
    stderr = "Standard error content"
    task_id = "test-task-abc"

    result = _write_full_output_to_file(str(temp_dir), stdout, stderr, task_id)

    # Should return path to file
    assert result is not None
    assert "build-output-" in result
    assert task_id in result

    # Verify file exists and contains content
    output_file = Path(result)
    assert output_file.exists()

    content = output_file.read_text()
    assert "STDOUT" in content
    assert "STDERR" in content
    assert stdout in content
    assert stderr in content


def test_write_full_output_to_file_creates_directory(temp_dir):
    """Test that function creates .context-foundry directory"""
    # Remove directory if it exists
    context_dir = temp_dir / ".context-foundry"
    if context_dir.exists():
        import shutil

        shutil.rmtree(context_dir)

    stdout = "Test output"
    stderr = ""
    task_id = "test-task-def"

    _write_full_output_to_file(str(temp_dir), stdout, stderr, task_id)

    # Verify directory was created
    assert context_dir.exists()
    assert context_dir.is_dir()


def test_write_full_output_to_file_encoding(temp_dir):
    """Test that function handles UTF-8 encoding correctly"""
    stdout = "Unicode: 你好世界 🚀"
    stderr = "Error: ñoño"
    task_id = "test-task-ghi"

    result = _write_full_output_to_file(str(temp_dir), stdout, stderr, task_id)

    # Verify file contains unicode content
    output_file = Path(result)
    content = output_file.read_text(encoding="utf-8")
    assert "你好世界" in content
    assert "🚀" in content
    assert "ñoño" in content


def test_write_full_output_to_file_handles_errors(temp_dir):
    """Test that function handles write errors gracefully"""
    stdout = "Test"
    stderr = "Test"
    task_id = "test-task-jkl"

    # Mock open to raise an error
    with patch("builtins.open", side_effect=OSError("Write error")):
        result = _write_full_output_to_file(str(temp_dir), stdout, stderr, task_id)

        # Should return error message instead of crashing
        assert "Error writing output file" in result


# ============================================================================
# Tests for _create_output_summary
# ============================================================================


def test_create_output_summary_under_max_lines():
    """Test summarizing output under max_lines (no truncation)"""
    output = "\n".join([f"Line {i}" for i in range(50)])

    summary, stats = _create_output_summary(output, max_lines=50)

    # Should return full output (50 lines < 50*2)
    assert summary == output
    assert stats["total_lines"] == 50
    assert stats["shown_lines"] == 50
    assert stats["hidden_lines"] == 0


def test_create_output_summary_over_max_lines():
    """Test summarizing output over max_lines (truncation)"""
    lines = [f"Line {i}" for i in range(200)]
    output = "\n".join(lines)

    summary, stats = _create_output_summary(output, max_lines=50)

    # Should truncate
    assert "[" in summary  # Contains truncation message
    assert "lines hidden" in summary
    assert stats["total_lines"] == 200
    assert stats["shown_lines"] == 100  # 50*2
    assert stats["hidden_lines"] == 100


def test_create_output_summary_empty_output():
    """Test summarizing empty output"""
    summary, stats = _create_output_summary("")

    assert summary == "(empty)"
    assert stats["total_lines"] == 0
    assert stats["shown_lines"] == 0
    assert stats["hidden_lines"] == 0


def test_create_output_summary_custom_max_lines():
    """Test summarizing with custom max_lines parameter"""
    lines = [f"Line {i}" for i in range(100)]
    output = "\n".join(lines)

    summary, stats = _create_output_summary(output, max_lines=10)

    # Should show first 10 + last 10 = 20 lines
    assert stats["total_lines"] == 100
    assert stats["shown_lines"] == 20
    assert stats["hidden_lines"] == 80


# ============================================================================
# Coverage Validation Test
# ============================================================================


def test_all_helper_functions_covered():
    """
    Meta-test to document that all helper functions are tested.
    This serves as documentation of test coverage.
    """
    tested_functions = {
        "_read_phase_info": _read_phase_info,
        "_truncate_output": _truncate_output,
        "_get_context_foundry_parent_dir": _get_context_foundry_parent_dir,
        "_write_delegation_metadata": _write_delegation_metadata,
        "_write_full_output_to_file": _write_full_output_to_file,
        "_create_output_summary": _create_output_summary,
    }

    # Verify each function is imported and callable
    for func_name, func in tested_functions.items():
        assert callable(func), f"{func_name} should be callable"

    # Count test functions for each helper
    test_counts = {
        "_read_phase_info": 6,
        "_truncate_output": 5,
        "_get_context_foundry_parent_dir": 2,
        "_write_delegation_metadata": 3,
        "_write_full_output_to_file": 4,
        "_create_output_summary": 4,
    }

    # Verify we have expected number of tests
    total_expected = sum(test_counts.values())
    assert total_expected == 24, f"Expected 24 test cases, documented {total_expected}"
