"""
Comprehensive test suite for tool_helpers module.

This test suite covers:
- ToolLimits configuration and validation
- Path utilities (conversion, formatting, edge cases)
- Truncation with recovery instructions
- Response formatting
- Configuration management
- Cross-platform compatibility
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.tool_helpers import (
    # Configuration
    ToolLimits,
    ToolHelpersConfig,
    get_default_limits,
    get_cached_default_limits,
    validate_limits,
    get_limit_for_operation,
    get_config,
    reset_config,
    # Path utilities
    to_relative_path,
    to_absolute_path,
    is_within_project,
    format_tool_output_paths,
    format_file_path_for_display,
    normalize_path_separators,
    get_common_path_prefix,
    relativize_paths_in_dict,
    # Truncation
    truncate_with_recovery,
    format_file_truncation,
    format_grep_truncation,
    format_command_truncation,
    truncate_line,
    count_tokens,
    TIKTOKEN_AVAILABLE,
    # Response formatting
    ToolResponse,
    format_file_read_output,
    format_grep_output,
    format_subprocess_output,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def temp_working_dir(tmp_path):
    """Create a temporary working directory."""
    return tmp_path


@pytest.fixture
def sample_file_content():
    """Generate sample file content."""
    return "line\n" * 1000


@pytest.fixture
def large_file_content():
    """Generate large file content for truncation tests."""
    return "line\n" * 60000  # Exceeds default max_lines


@pytest.fixture
def clean_env():
    """Clean environment variables before and after test."""
    old_env = os.environ.copy()
    # Remove all CF_ variables
    for key in list(os.environ.keys()):
        if key.startswith('CF_'):
            del os.environ[key]
    yield
    # Restore
    os.environ.clear()
    os.environ.update(old_env)
    # Reset config cache
    reset_config()


# ============================================================================
# Test ToolLimits
# ============================================================================

class TestToolLimits:
    """Test limits configuration and validation."""

    def test_default_limits(self, clean_env):
        """Test default limits are reasonable."""
        limits = get_default_limits()
        assert limits.max_file_read_lines == 50000
        assert limits.max_file_read_chars == 500000
        assert limits.max_grep_matches == 10000
        assert limits.use_relative_paths is True

    def test_environment_override_int(self, clean_env):
        """Test environment variable overrides for integers."""
        os.environ['CF_LIMIT_FILE_READ_CHARS'] = '100000'
        limits = get_default_limits()
        assert limits.max_file_read_chars == 100000

    def test_environment_override_bool(self, clean_env):
        """Test environment variable overrides for booleans."""
        os.environ['CF_USE_RELATIVE_PATHS'] = 'false'
        limits = get_default_limits()
        assert limits.use_relative_paths is False

        os.environ['CF_USE_RELATIVE_PATHS'] = 'true'
        limits = get_default_limits()
        assert limits.use_relative_paths is True

    def test_environment_override_invalid(self, clean_env):
        """Test invalid environment variable values use defaults."""
        os.environ['CF_LIMIT_FILE_READ_CHARS'] = 'invalid'
        limits = get_default_limits()
        assert limits.max_file_read_chars == 500000  # Default

    def test_validate_limits_valid(self):
        """Test validation passes for valid limits."""
        limits = ToolLimits()
        is_valid, errors = validate_limits(limits)
        assert is_valid
        assert len(errors) == 0

    def test_validate_limits_negative(self):
        """Test validation fails for negative values."""
        with pytest.raises(ValueError):
            ToolLimits(max_file_read_chars=-1000)

    def test_validate_limits_too_large(self):
        """Test validation fails for excessively large values."""
        with pytest.raises(ValueError):
            ToolLimits(max_file_read_chars=20_000_000)  # > 10MB limit

    def test_validate_limits_invalid_strategy(self):
        """Test validation fails for invalid truncation strategy."""
        with pytest.raises(ValueError):
            ToolLimits(truncation_strategy='invalid')

    def test_get_limit_for_operation_file_read(self):
        """Test getting limits for file_read operation."""
        limits = get_default_limits()
        op_limits = get_limit_for_operation('file_read', limits)
        assert 'max_chars' in op_limits
        assert 'max_lines' in op_limits
        assert op_limits['max_chars'] == 500000

    def test_get_limit_for_operation_grep(self):
        """Test getting limits for grep operation."""
        limits = get_default_limits()
        op_limits = get_limit_for_operation('grep', limits)
        assert 'max_matches' in op_limits
        assert 'max_chars' in op_limits

    def test_get_limit_for_operation_invalid(self):
        """Test getting limits for invalid operation raises error."""
        with pytest.raises(ValueError):
            get_limit_for_operation('invalid_operation')

    def test_cached_default_limits(self, clean_env):
        """Test cached limits avoid repeated environment reads."""
        os.environ['CF_LIMIT_FILE_READ_CHARS'] = '100000'
        limits1 = get_cached_default_limits()
        assert limits1.max_file_read_chars == 100000

        # Change environment
        os.environ['CF_LIMIT_FILE_READ_CHARS'] = '200000'
        limits2 = get_cached_default_limits()
        # Should still be cached value
        assert limits2.max_file_read_chars == 100000


# ============================================================================
# Test Path Utilities
# ============================================================================

class TestPathUtils:
    """Test path conversion and formatting."""

    def test_to_relative_path_basic(self, temp_working_dir):
        """Test basic absolute to relative conversion."""
        abs_path = temp_working_dir / "tools" / "cache.py"
        relative = to_relative_path(abs_path, temp_working_dir)
        assert relative == "tools/cache.py"

    def test_to_relative_path_already_relative(self, temp_working_dir):
        """Test relative path returns as-is."""
        relative = to_relative_path("tools/cache.py", temp_working_dir)
        assert relative == "tools/cache.py"

    def test_to_relative_path_outside_working_dir(self, temp_working_dir):
        """Test path outside working dir returns absolute."""
        outside_path = "/etc/passwd"
        result = to_relative_path(outside_path, temp_working_dir, strict=False)
        assert result == outside_path

    def test_to_relative_path_outside_strict(self, temp_working_dir):
        """Test strict mode raises error for outside paths."""
        with pytest.raises(ValueError):
            to_relative_path("/etc/passwd", temp_working_dir, strict=True)

    def test_to_absolute_path(self, temp_working_dir):
        """Test relative to absolute conversion."""
        relative = "tools/cache.py"
        absolute = to_absolute_path(relative, temp_working_dir)
        expected = str(temp_working_dir / "tools" / "cache.py")
        assert absolute == expected

    def test_to_absolute_path_already_absolute(self):
        """Test absolute path returns resolved."""
        abs_path = "/usr/bin/python"
        result = to_absolute_path(abs_path)
        assert result.startswith("/")

    def test_is_within_project_true(self, temp_working_dir):
        """Test path within project returns True."""
        path = temp_working_dir / "tools" / "cache.py"
        assert is_within_project(path, temp_working_dir) is True

    def test_is_within_project_false(self, temp_working_dir):
        """Test path outside project returns False."""
        assert is_within_project("/etc/passwd", temp_working_dir) is False

    def test_format_tool_output_paths(self, temp_working_dir):
        """Test converting paths in tool output."""
        output = f"Error in {temp_working_dir}/tools/cache.py:42"
        formatted = format_tool_output_paths(output, temp_working_dir)
        assert "tools/cache.py:42" in formatted
        assert str(temp_working_dir) not in formatted

    def test_format_tool_output_paths_preserves_system(self, temp_working_dir):
        """Test system paths are preserved."""
        output = "Using /usr/bin/python"
        formatted = format_tool_output_paths(output, temp_working_dir)
        assert "/usr/bin/python" in formatted  # Preserved

    def test_format_file_path_for_display(self, temp_working_dir):
        """Test formatting path for display."""
        path = temp_working_dir / "tools" / "cache" / "manager.py"
        formatted = format_file_path_for_display(path, temp_working_dir)
        assert formatted == "tools/cache/manager.py"

    def test_format_file_path_for_display_truncate(self, temp_working_dir):
        """Test path truncation for long paths."""
        path = temp_working_dir / "very" / "long" / "path" / "to" / "file.py"
        formatted = format_file_path_for_display(path, temp_working_dir, max_length=20)
        assert len(formatted) <= 20
        assert "..." in formatted

    def test_normalize_path_separators(self):
        """Test normalizing backslashes to forward slashes."""
        path = "tools\\\\cache\\\\manager.py"
        normalized = normalize_path_separators(path)
        assert normalized == "tools/cache/manager.py"

    def test_get_common_path_prefix(self, temp_working_dir):
        """Test finding common prefix of paths."""
        paths = [
            temp_working_dir / "tools" / "cache.py",
            temp_working_dir / "tools" / "metrics.py",
            temp_working_dir / "tests" / "test.py"
        ]
        common = get_common_path_prefix(paths)
        assert common == str(temp_working_dir)

    def test_get_common_path_prefix_empty(self):
        """Test empty path list returns empty string."""
        assert get_common_path_prefix([]) == ""

    def test_relativize_paths_in_dict(self, temp_working_dir):
        """Test converting paths in dictionary."""
        data = {
            'file': str(temp_working_dir / "tools" / "cache.py"),
            'line': 42
        }
        result = relativize_paths_in_dict(data, temp_working_dir)
        assert result['file'] == "tools/cache.py"
        assert result['line'] == 42

    def test_relativize_paths_in_dict_nested(self, temp_working_dir):
        """Test converting paths in nested dictionary."""
        data = {
            'error': {
                'file': str(temp_working_dir / "tools" / "cache.py"),
                'message': 'Error'
            }
        }
        result = relativize_paths_in_dict(data, temp_working_dir)
        assert result['error']['file'] == "tools/cache.py"


# ============================================================================
# Test Truncation
# ============================================================================

class TestTruncation:
    """Test smart truncation with recovery instructions."""

    def test_truncate_with_recovery_no_truncation(self):
        """Test no truncation when under limits."""
        content = "short content"
        truncated, was_truncated, meta = truncate_with_recovery(
            content, max_chars=1000, max_lines=100
        )
        assert truncated == content
        assert was_truncated is False
        assert meta['truncation_reason'] is None

    def test_truncate_with_recovery_line_limit(self):
        """Test truncation by line limit."""
        content = "line\n" * 100
        truncated, was_truncated, meta = truncate_with_recovery(
            content, max_chars=100000, max_lines=50
        )
        assert was_truncated is True
        assert meta['truncated_lines'] == 50
        assert 'recovery_instructions' in meta

    def test_truncate_with_recovery_char_limit(self):
        """Test truncation by character limit."""
        content = "a" * 10000
        truncated, was_truncated, meta = truncate_with_recovery(
            content, max_chars=5000, max_lines=10000
        )
        assert was_truncated is True
        assert len(truncated) <= 5000

    def test_truncate_with_recovery_file_read(self):
        """Test truncation for file read operation."""
        content = "line\n" * 60000  # Exceeds default max_lines
        truncated, was_truncated, meta = truncate_with_recovery(
            content,
            file_path="tools/cache.py",
            operation_type='file_read'
        )
        assert was_truncated is True
        assert 'read_file' in meta['recovery_instructions']

    def test_truncate_with_recovery_grep(self):
        """Test truncation for grep operation."""
        content = "match\n" * 20000
        truncated, was_truncated, meta = truncate_with_recovery(
            content,
            operation_type='grep'
        )
        assert was_truncated is True
        assert 'search pattern' in meta['recovery_instructions'].lower()

    def test_format_file_truncation(self):
        """Test formatting truncated file content."""
        content = "line\n" * 60000
        formatted, meta = format_file_truncation(content, "tools/cache.py")
        assert meta['was_truncated'] is True
        assert "FILE TRUNCATED" in formatted
        assert "recovery" in formatted.lower()

    def test_format_grep_truncation(self):
        """Test formatting truncated grep results."""
        results = "match\n" * 20000
        formatted, meta = format_grep_truncation(results, "test_pattern")
        assert meta['was_truncated'] is True
        assert "GREP RESULTS TRUNCATED" in formatted

    def test_format_command_truncation(self):
        """Test formatting truncated command output."""
        output = "output\n" * 30000
        formatted, meta = format_command_truncation(output, "npm test", exit_code=0)
        assert meta['was_truncated'] is True
        assert "COMMAND OUTPUT TRUNCATED" in formatted
        assert meta['exit_code'] == 0

    def test_truncate_line(self):
        """Test truncating a single very long line."""
        long_line = "a" * 2000
        truncated = truncate_line(long_line, max_length=100)
        assert len(truncated) < len(long_line)
        assert "..." in truncated
        assert "truncated" in truncated

    def test_truncate_line_no_truncation(self):
        """Test line under limit not truncated."""
        short_line = "short"
        truncated = truncate_line(short_line, max_length=100)
        assert truncated == short_line

    def test_count_tokens(self):
        """Test token counting."""
        text = "Hello world! This is a test."
        tokens = count_tokens(text)
        assert tokens > 0
        # Should be roughly len(text) // 4
        assert tokens >= len(text) // 5
        assert tokens <= len(text) // 3

    def test_count_tokens_empty(self):
        """Test counting tokens in empty string."""
        assert count_tokens("") == 0


# ============================================================================
# Test Response Formatter
# ============================================================================

class TestResponseFormatter:
    """Test standardized tool response formatting."""

    def test_tool_response_success(self):
        """Test successful response formatting."""
        response = ToolResponse(
            success=True,
            data="file content",
            metadata={'file_path': '/path/to/file.py', 'lines': 100}
        )
        formatted = response.format_for_agent()
        assert "✅ Success" in formatted
        assert "file content" in formatted

    def test_tool_response_failure(self):
        """Test failure response formatting."""
        response = ToolResponse(
            success=False,
            data=None,
            error="File not found"
        )
        formatted = response.format_for_agent()
        assert "❌ Failed" in formatted
        assert "File not found" in formatted

    def test_tool_response_with_metadata(self, temp_working_dir):
        """Test response with metadata formatting."""
        response = ToolResponse(
            success=True,
            data="content",
            metadata={
                'file_path': str(temp_working_dir / "tools" / "cache.py"),
                'lines': 150
            },
            working_dir=temp_working_dir
        )
        formatted = response.format_for_agent()
        assert "tools/cache.py" in formatted  # Relative path
        assert "150" in formatted

    def test_file_read_response(self, temp_working_dir):
        """Test file read response creation."""
        content = "file content here"
        response = ToolResponse.file_read_response(
            content=content,
            file_path=temp_working_dir / "test.py",
            working_dir=temp_working_dir
        )
        assert response.success is True
        assert response.metadata['file_path'] == temp_working_dir / "test.py"

    def test_file_read_response_truncated(self, temp_working_dir):
        """Test file read response with truncation."""
        content = "line\n" * 60000  # Exceeds limit
        response = ToolResponse.file_read_response(
            content=content,
            file_path=temp_working_dir / "large.py",
            working_dir=temp_working_dir
        )
        assert response.metadata['was_truncated'] is True
        formatted = response.format_for_agent()
        assert "TRUNCATED" in formatted

    def test_grep_response(self):
        """Test grep response creation."""
        results = "file1:match\nfile2:match\n"
        response = ToolResponse.grep_response(
            results=results,
            pattern="test",
            num_matches=2
        )
        assert response.success is True
        assert response.metadata['matches'] == 2
        assert response.metadata['pattern'] == "test"

    def test_subprocess_response_success(self):
        """Test subprocess response with success."""
        output = "All tests passed"
        response = ToolResponse.subprocess_response(
            output=output,
            command="npm test",
            exit_code=0
        )
        assert response.success is True
        assert response.metadata['exit_code'] == 0

    def test_subprocess_response_failure(self):
        """Test subprocess response with failure."""
        output = "Error: tests failed"
        response = ToolResponse.subprocess_response(
            output=output,
            command="npm test",
            exit_code=1
        )
        assert response.success is False
        assert response.error is not None

    def test_error_response(self):
        """Test error response creation."""
        response = ToolResponse.error_response(
            error="File not found",
            operation="file_read",
            details={'path': '/missing/file.txt'}
        )
        assert response.success is False
        assert response.error == "File not found"
        assert response.metadata['operation'] == "file_read"

    def test_format_file_read_output(self, temp_working_dir):
        """Test convenience function for file read output."""
        content = "file content"
        output = format_file_read_output(
            content,
            temp_working_dir / "test.py",
            temp_working_dir
        )
        assert "✅ Success" in output
        assert "file content" in output

    def test_format_grep_output(self):
        """Test convenience function for grep output."""
        results = "match1\nmatch2"
        output = format_grep_output(results, "pattern", num_matches=2)
        assert "✅ Success" in output
        assert "match1" in output

    def test_format_subprocess_output(self):
        """Test convenience function for subprocess output."""
        output_text = "command output"
        output = format_subprocess_output(output_text, "echo test", exit_code=0)
        assert "✅ Success" in output
        assert "command output" in output


# ============================================================================
# Test Configuration
# ============================================================================

class TestConfiguration:
    """Test configuration management."""

    def test_config_default(self, clean_env):
        """Test default configuration."""
        config = ToolHelpersConfig.from_env()
        assert config.limits.max_file_read_chars == 500000

    def test_config_custom_limits(self):
        """Test configuration with custom limits."""
        limits = ToolLimits(max_file_read_chars=100000)
        config = ToolHelpersConfig(limits=limits)
        assert config.limits.max_file_read_chars == 100000

    def test_config_get_limit(self):
        """Test getting limit from configuration."""
        config = ToolHelpersConfig()
        limit = config.get_limit('file_read', 'max_chars')
        assert limit == 500000

    def test_config_debug_mode(self, clean_env):
        """Test debug mode configuration."""
        os.environ['CF_DEBUG'] = 'true'
        config = ToolHelpersConfig.from_env()
        assert config.debug is True

    def test_get_config_singleton(self, clean_env):
        """Test global config is singleton."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_reset_config(self, clean_env):
        """Test resetting configuration."""
        config1 = get_config()
        reset_config()
        config2 = get_config()
        assert config1 is not config2


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Test integration between modules."""

    def test_end_to_end_file_read(self, temp_working_dir):
        """Test complete file read flow."""
        # Create test file
        test_file = temp_working_dir / "test.py"
        test_file.write_text("print('hello')\n" * 100)

        # Read and format
        content = test_file.read_text()
        response = ToolResponse.file_read_response(
            content=content,
            file_path=test_file,
            working_dir=temp_working_dir
        )

        formatted = response.format_for_agent()

        # Verify
        assert "✅ Success" in formatted
        assert "test.py" in formatted  # Relative path
        assert "print('hello')" in formatted

    def test_end_to_end_truncation_with_paths(self, temp_working_dir):
        """Test truncation with path conversion."""
        # Large content with paths
        content = f"Error in {temp_working_dir}/tools/cache.py:42\n" * 30000

        response = ToolResponse.subprocess_response(
            output=content,
            command="npm test",
            exit_code=1,
            working_dir=temp_working_dir
        )

        formatted = response.format_for_agent()

        # Should be truncated
        assert response.metadata['was_truncated'] is True
        # Paths should be relative
        assert "tools/cache.py" in formatted
        # Should not contain absolute paths
        assert str(temp_working_dir) not in formatted or "TRUNCATED" in formatted


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Test performance characteristics."""

    def test_path_conversion_performance(self, temp_working_dir, benchmark=None):
        """Test path conversion is fast."""
        path = temp_working_dir / "tools" / "cache" / "manager.py"

        # Should be very fast (< 1ms for 1000 conversions)
        import time
        start = time.time()
        for _ in range(1000):
            to_relative_path(path, temp_working_dir)
        elapsed = time.time() - start

        assert elapsed < 0.1  # 100ms for 1000 conversions

    def test_truncation_performance(self, benchmark=None):
        """Test truncation is fast."""
        content = "line\n" * 10000

        import time
        start = time.time()
        for _ in range(100):
            truncate_with_recovery(content, max_lines=5000)
        elapsed = time.time() - start

        assert elapsed < 1.0  # 1s for 100 truncations


# ============================================================================
# Cross-Platform Tests
# ============================================================================

class TestCrossPlatform:
    """Test cross-platform compatibility."""

    def test_windows_path_separators(self):
        """Test handling Windows-style paths."""
        windows_path = "C:\\\\Users\\\\name\\\\project\\\\file.py"
        normalized = normalize_path_separators(windows_path)
        assert "\\\\" not in normalized
        assert "/" in normalized

    def test_unix_path_separators(self):
        """Test handling Unix-style paths."""
        unix_path = "/Users/name/project/file.py"
        normalized = normalize_path_separators(unix_path)
        assert normalized == unix_path


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
