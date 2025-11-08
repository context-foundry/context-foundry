"""
Unit tests for tools/tool_helpers/path_utils.py

Tests:
- to_relative_path: Absolute to relative path conversion
- to_absolute_path: Relative to absolute path conversion
- is_within_project: Project boundary detection
- format_tool_output_paths: Batch path conversion in text
- format_file_path_for_display: Display formatting with truncation
- normalize_path_separators: Cross-platform path normalization
- get_common_path_prefix: Common prefix detection
- relativize_paths_in_dict: Dictionary path conversion
"""

import pytest
import tempfile
import os
from pathlib import Path

# Import path utils module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.tool_helpers.path_utils import (
    to_relative_path,
    to_absolute_path,
    is_within_project,
    format_tool_output_paths,
    format_file_path_for_display,
    normalize_path_separators,
    get_common_path_prefix,
    relativize_paths_in_dict
)


class TestToRelativePath:
    """Test absolute to relative path conversion."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_absolute_to_relative_basic(self):
        """Test basic absolute to relative conversion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            abs_path = os.path.join(tmpdir, "tools", "cache.py")
            result = to_relative_path(abs_path, tmpdir)
            assert result == "tools/cache.py" or result == f"tools{os.sep}cache.py"

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_already_relative_unchanged(self):
        """Test that relative paths are returned unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            relative_path = "tools/cache.py"
            result = to_relative_path(relative_path, tmpdir)
            assert result == relative_path

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_outside_working_dir_returns_absolute(self):
        """Test that paths outside working dir return absolute (strict=False)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            outside_path = "/tmp/other.py"
            result = to_relative_path(outside_path, tmpdir, strict=False)
            # Should return absolute path when outside working dir
            assert os.path.isabs(result)

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_strict_mode_raises_outside_working_dir(self):
        """Test that strict=True raises ValueError for paths outside working dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            outside_path = "/tmp/other.py"
            with pytest.raises(ValueError, match="outside working directory"):
                to_relative_path(outside_path, tmpdir, strict=True)

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_default_working_dir_uses_cwd(self):
        """Test that working_dir=None uses current working directory."""
        # This should not raise an error
        result = to_relative_path(__file__)
        assert isinstance(result, str)

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_path_object_input(self):
        """Test that Path objects are accepted as input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path_obj = Path(tmpdir) / "tools" / "cache.py"
            result = to_relative_path(path_obj, tmpdir)
            assert "tools" in result and "cache.py" in result


class TestToAbsolutePath:
    """Test relative to absolute path conversion."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_relative_to_absolute_basic(self):
        """Test basic relative to absolute conversion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            relative_path = "tools/cache.py"
            result = to_absolute_path(relative_path, tmpdir)
            assert os.path.isabs(result)
            assert "tools" in result
            assert "cache.py" in result

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_already_absolute_unchanged(self):
        """Test that absolute paths are returned (resolved)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            abs_path = os.path.join(tmpdir, "test.py")
            result = to_absolute_path(abs_path, tmpdir)
            assert os.path.isabs(result)

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_default_working_dir_uses_cwd(self):
        """Test that working_dir=None uses current working directory."""
        result = to_absolute_path("test.py")
        assert os.path.isabs(result)
        assert result.endswith("test.py")

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_path_object_input(self):
        """Test that Path objects are accepted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path_obj = Path("tools/cache.py")
            result = to_absolute_path(path_obj, tmpdir)
            assert os.path.isabs(result)


class TestIsWithinProject:
    """Test project boundary detection."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_path_within_project_returns_true(self):
        """Test that paths within project return True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path_inside = os.path.join(tmpdir, "tools", "cache.py")
            assert is_within_project(path_inside, tmpdir) is True

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_path_outside_project_returns_false(self):
        """Test that paths outside project return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path_outside = "/tmp/other.py"
            assert is_within_project(path_outside, tmpdir) is False

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_default_working_dir_uses_cwd(self):
        """Test that working_dir=None uses current directory."""
        # Test with current file (should be within project)
        result = is_within_project(__file__)
        assert isinstance(result, bool)

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_same_directory_returns_true(self):
        """Test that the working dir itself is considered within project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert is_within_project(tmpdir, tmpdir) is True


class TestFormatToolOutputPaths:
    """Test batch path conversion in text output."""

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_convert_single_absolute_path(self):
        """Test converting single absolute path in output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            abs_path = os.path.join(tmpdir, "tools", "cache.py")
            output = f"Error in {abs_path}:42"
            result = format_tool_output_paths(output, tmpdir)
            assert tmpdir not in result
            assert "tools" in result
            assert "cache.py" in result

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_convert_multiple_paths(self):
        """Test converting multiple paths in output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = os.path.join(tmpdir, "tools", "cache.py")
            path2 = os.path.join(tmpdir, "tests", "test.py")
            output = f"Error in {path1}:42 and {path2}:100"
            result = format_tool_output_paths(output, tmpdir)
            assert tmpdir not in result
            assert "tools/cache.py" in result or "tools" in result
            assert "tests/test.py" in result or "tests" in result

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_preserve_system_paths(self):
        """Test that system paths are preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = "Using /usr/bin/python3"
            result = format_tool_output_paths(output, tmpdir)
            assert "/usr/bin/python3" in result

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_custom_preserve_patterns(self):
        """Test custom preserve patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "special", "file.py")
            output = f"File: {path}"
            # Preserve paths containing 'special'
            result = format_tool_output_paths(
                output,
                tmpdir,
                preserve_patterns=[r'.*special.*']
            )
            # Path should be preserved since it matches pattern
            assert "special" in result


class TestFormatFilePathForDisplay:
    """Test display formatting with truncation."""

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_no_truncation_under_limit(self):
        """Test that short paths are not truncated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.py")
            result = format_file_path_for_display(path, tmpdir, max_length=50)
            assert "..." not in result

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_truncation_over_limit(self):
        """Test that long paths are truncated with ...."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "very", "long", "path", "to", "file.py")
            result = format_file_path_for_display(path, tmpdir, max_length=20)
            assert "..." in result
            assert len(result) <= 23  # Allow some tolerance

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_no_max_length_returns_relative(self):
        """Test that max_length=None returns full relative path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "tools", "cache.py")
            result = format_file_path_for_display(path, tmpdir, max_length=None)
            assert "..." not in result
            assert "tools" in result

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_truncation_preserves_first_and_last(self):
        """Test that truncation keeps first and last parts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "tools", "very", "deep", "file.py")
            result = format_file_path_for_display(path, tmpdir, max_length=25)
            # Should have first part and last part
            if "..." in result:
                assert "file.py" in result or "tools" in result


class TestNormalizePathSeparators:
    """Test cross-platform path normalization."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_windows_to_unix_separators(self):
        """Test converting backslashes to forward slashes."""
        windows_path = "tools\\cache\\manager.py"
        result = normalize_path_separators(windows_path)
        assert result == "tools/cache/manager.py"

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_double_backslash_to_forward_slash(self):
        """Test converting double backslashes."""
        path = "tools\\\\cache\\\\manager.py"
        result = normalize_path_separators(path)
        assert "\\" not in result
        assert "/" in result

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_unix_path_unchanged(self):
        """Test that Unix paths remain unchanged."""
        unix_path = "tools/cache/manager.py"
        result = normalize_path_separators(unix_path)
        assert result == unix_path

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_mixed_separators_normalized(self):
        """Test normalizing mixed separators."""
        mixed = "tools/cache\\manager.py"
        result = normalize_path_separators(mixed)
        assert result == "tools/cache/manager.py"


class TestGetCommonPathPrefix:
    """Test common prefix detection."""

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_common_prefix_same_parent(self):
        """Test finding common prefix for paths in same parent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = [
                os.path.join(tmpdir, "tools", "cache.py"),
                os.path.join(tmpdir, "tools", "metrics.py"),
                os.path.join(tmpdir, "tests", "test.py")
            ]
            result = get_common_path_prefix(paths)
            # Common prefix should be tmpdir
            assert Path(result).resolve() == Path(tmpdir).resolve()

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_common_prefix_different_depths(self):
        """Test common prefix with different depth paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = [
                os.path.join(tmpdir, "a", "b", "c.py"),
                os.path.join(tmpdir, "a", "d.py"),
                os.path.join(tmpdir, "e.py")
            ]
            result = get_common_path_prefix(paths)
            assert Path(result).resolve() == Path(tmpdir).resolve()

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_empty_list_returns_empty_string(self):
        """Test that empty list returns empty string."""
        result = get_common_path_prefix([])
        assert result == ""

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_single_path_returns_itself(self):
        """Test that single path returns itself."""
        path = "/Users/test/project/file.py"
        result = get_common_path_prefix([path])
        assert Path(result).resolve() == Path(path).resolve()


class TestRelativizePathsInDict:
    """Test dictionary path conversion."""

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_convert_single_path_in_dict(self):
        """Test converting single path in dictionary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            abs_path = os.path.join(tmpdir, "tools", "cache.py")
            data = {"file": abs_path, "line": 42}
            result = relativize_paths_in_dict(data, tmpdir)
            assert tmpdir not in result["file"]
            assert "tools" in result["file"] or "cache.py" in result["file"]
            assert result["line"] == 42

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_convert_nested_dict(self):
        """Test converting paths in nested dictionaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            abs_path = os.path.join(tmpdir, "tools", "cache.py")
            data = {
                "outer": {
                    "inner": {"file": abs_path}
                }
            }
            result = relativize_paths_in_dict(data, tmpdir)
            assert tmpdir not in str(result)
            inner_file = result["outer"]["inner"]["file"]
            assert "tools" in inner_file or "cache.py" in inner_file

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_convert_list_of_paths(self):
        """Test converting paths in lists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = [
                os.path.join(tmpdir, "tools", "a.py"),
                os.path.join(tmpdir, "tools", "b.py")
            ]
            data = {"files": paths}
            result = relativize_paths_in_dict(data, tmpdir)
            assert len(result["files"]) == 2
            for file_path in result["files"]:
                assert tmpdir not in file_path

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_non_path_strings_unchanged(self):
        """Test that non-path strings are not modified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {
                "name": "test",
                "description": "A test description",
                "count": 42
            }
            result = relativize_paths_in_dict(data, tmpdir)
            assert result == data

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_path_keys_filter(self):
        """Test that path_keys parameter filters which keys to process."""
        with tempfile.TemporaryDirectory() as tmpdir:
            abs_path = os.path.join(tmpdir, "tools", "cache.py")
            data = {
                "file": abs_path,
                "other_path": abs_path
            }
            result = relativize_paths_in_dict(data, tmpdir, path_keys=["file"])
            # Only 'file' key should be converted
            assert tmpdir not in result["file"]
            assert tmpdir in result["other_path"]  # Should remain absolute


class TestPathUtilsIntegration:
    """Integration tests for path utilities."""

    @pytest.mark.integration
    @pytest.mark.tier2
    def test_round_trip_conversion(self):
        """Test converting absolute → relative → absolute."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_abs = os.path.join(tmpdir, "tools", "cache.py")
            relative = to_relative_path(original_abs, tmpdir)
            back_to_abs = to_absolute_path(relative, tmpdir)
            
            # Should end up with same path (resolved)
            assert Path(back_to_abs).resolve() == Path(original_abs).resolve()

    @pytest.mark.integration
    @pytest.mark.tier2
    def test_format_output_and_display(self):
        """Test using format_tool_output_paths and format_file_path_for_display together."""
        with tempfile.TemporaryDirectory() as tmpdir:
            long_path = os.path.join(tmpdir, "very", "long", "path", "to", "file.py")
            output = f"Error in {long_path}:100"
            
            # First format the output
            formatted = format_tool_output_paths(output, tmpdir)
            
            # Result should not contain tmpdir
            assert tmpdir not in formatted
            assert "file.py" in formatted

    @pytest.mark.integration
    @pytest.mark.tier2
    def test_is_within_project_matches_conversion(self):
        """Test that is_within_project aligns with successful conversion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path_inside = os.path.join(tmpdir, "tools", "cache.py")
            path_outside = "/tmp/other.py"
            
            # Inside path should convert to relative
            assert is_within_project(path_inside, tmpdir)
            relative = to_relative_path(path_inside, tmpdir, strict=False)
            assert not os.path.isabs(relative)
            
            # Outside path should remain absolute (strict=False)
            assert not is_within_project(path_outside, tmpdir)
            result = to_relative_path(path_outside, tmpdir, strict=False)
            assert os.path.isabs(result)
