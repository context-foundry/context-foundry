"""
Unit tests for Smart Incremental Builds - Phase 1 Cache System

Tests:
- Scout cache: Task hashing, cache hit/miss, TTL expiration
- Test cache: File hashing, change detection, cache invalidation
- Cache manager: Stats, cleanup, size limits
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import time
import json

# Import cache modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.cache import (
    get_cache_dir,
    hash_string,
    is_cache_valid,
    save_cache_metadata,
    load_cache_metadata,
    get_cache_stats
)
from tools.cache.scout_cache import (
    normalize_task_description,
    generate_scout_cache_key,
    get_cached_scout_report,
    save_scout_report_to_cache,
    clear_scout_cache,
    get_scout_cache_stats
)
from tools.cache.test_cache import (
    hash_file,
    compute_file_hashes,
    get_cached_test_results,
    save_test_results_to_cache,
    clear_test_cache,
    get_test_cache_stats
)
from tools.cache.cache_manager import CacheManager


class TestScoutCache:
    """Test Scout cache functionality."""

    def test_normalize_task_description(self):
        """Test task normalization for better cache matching."""
        task1 = "Build a weather app with React"
        task2 = "Build  a   weather    app   with   React"
        task3 = "BUILD A WEATHER APP WITH REACT"

        assert normalize_task_description(task1) == normalize_task_description(task2)
        assert normalize_task_description(task1) == normalize_task_description(task3)

    def test_generate_cache_key_consistency(self):
        """Test that same inputs generate same cache key."""
        key1 = generate_scout_cache_key("Build todo app", "new_project", "/tmp/project")
        key2 = generate_scout_cache_key("Build todo app", "new_project", "/tmp/project")

        assert key1 == key2

    def test_generate_cache_key_different_tasks(self):
        """Test that different tasks generate different keys."""
        key1 = generate_scout_cache_key("Build todo app", "new_project", "/tmp/project")
        key2 = generate_scout_cache_key("Build weather app", "new_project", "/tmp/project")

        assert key1 != key2

    def test_scout_cache_save_and_retrieve(self):
        """Test saving and retrieving Scout reports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = "Build a test app"
            mode = "new_project"
            report_content = "# Scout Report\nThis is a test report."

            # Save report
            save_scout_report_to_cache(task, mode, tmpdir, report_content)

            # Retrieve report
            cached = get_cached_scout_report(task, mode, tmpdir)

            assert cached == report_content

    def test_scout_cache_miss_different_task(self):
        """Test cache miss for different task."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task1 = "Build a test app"
            task2 = "Build a different app"
            mode = "new_project"
            report_content = "# Scout Report"

            # Save report for task1
            save_scout_report_to_cache(task1, mode, tmpdir, report_content)

            # Try to retrieve with task2 (should miss)
            cached = get_cached_scout_report(task2, mode, tmpdir)

            assert cached is None

    def test_scout_cache_ttl_expiration(self):
        """Test that cache expires after TTL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = "Build a test app"
            mode = "new_project"
            report_content = "# Scout Report"

            # Save report
            save_scout_report_to_cache(task, mode, tmpdir, report_content)

            # Retrieve with 0 hour TTL (should be expired)
            cached = get_cached_scout_report(task, mode, tmpdir, ttl_hours=0)

            assert cached is None

    def test_scout_cache_stats(self):
        """Test Scout cache statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = "Build a test app"
            mode = "new_project"
            report_content = "# Scout Report"

            # Initially no cache entries
            stats_before = get_scout_cache_stats(tmpdir)
            assert stats_before["total_entries"] == 0

            # Save report
            save_scout_report_to_cache(task, mode, tmpdir, report_content)

            # Check stats after save
            stats_after = get_scout_cache_stats(tmpdir)
            assert stats_after["total_entries"] == 1
            assert stats_after["valid_entries"] == 1
            assert stats_after["expired_entries"] == 0

    def test_clear_scout_cache(self):
        """Test clearing Scout cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = "Build a test app"
            mode = "new_project"
            report_content = "# Scout Report"

            # Save multiple reports
            save_scout_report_to_cache(task, mode, tmpdir, report_content)
            save_scout_report_to_cache(task + " v2", mode, tmpdir, report_content)

            # Verify saved
            stats = get_scout_cache_stats(tmpdir)
            assert stats["total_entries"] == 2

            # Clear cache
            deleted = clear_scout_cache(tmpdir)
            assert deleted == 2

            # Verify cleared
            stats_after = get_scout_cache_stats(tmpdir)
            assert stats_after["total_entries"] == 0


class TestTestCache:
    """Test result cache functionality."""

    def test_hash_file(self):
        """Test file hashing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("Hello, World!")

            hash1 = hash_file(file_path)
            assert len(hash1) == 64  # SHA256 hex

            # Same content = same hash
            hash2 = hash_file(file_path)
            assert hash1 == hash2

            # Different content = different hash
            file_path.write_text("Different content")
            hash3 = hash_file(file_path)
            assert hash1 != hash3

    def test_compute_file_hashes(self):
        """Test computing hashes for all source files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some source files
            (Path(tmpdir) / "src").mkdir()
            (Path(tmpdir) / "src" / "main.py").write_text("print('hello')")
            (Path(tmpdir) / "src" / "utils.py").write_text("def func(): pass")
            (Path(tmpdir) / "README.md").write_text("# Project")  # Should be ignored (not source)

            hashes = compute_file_hashes(tmpdir)

            # Should have 2 .py files
            assert len(hashes) == 2
            assert "src/main.py" in hashes
            assert "src/utils.py" in hashes
            assert "README.md" not in hashes  # Not a source file

    def test_test_cache_save_and_retrieve(self):
        """Test saving and retrieving test results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source files
            (Path(tmpdir) / "src").mkdir()
            (Path(tmpdir) / "src" / "main.py").write_text("print('hello')")

            # Save test results
            test_results = {
                "success": True,
                "passed": 25,
                "total": 25,
                "duration": 10.5,
                "test_command": "npm test"
            }
            save_test_results_to_cache(tmpdir, test_results)

            # Retrieve (should hit cache - no file changes)
            cached = get_cached_test_results(tmpdir)

            assert cached is not None
            assert cached["success"] == True
            assert cached["passed"] == 25
            assert cached["total"] == 25

    def test_test_cache_miss_on_file_change(self):
        """Test cache miss when files change."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file
            (Path(tmpdir) / "src").mkdir()
            src_file = Path(tmpdir) / "src" / "main.py"
            src_file.write_text("print('hello')")

            # Save test results
            test_results = {
                "success": True,
                "passed": 25,
                "total": 25,
                "duration": 10.5
            }
            save_test_results_to_cache(tmpdir, test_results)

            # Modify source file
            src_file.write_text("print('world')")

            # Retrieve (should miss - file changed)
            cached = get_cached_test_results(tmpdir)

            assert cached is None

    def test_test_cache_stats(self):
        """Test cache statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initially no cache
            stats_before = get_test_cache_stats(tmpdir)
            assert stats_before["has_cached_results"] == False

            # Create source files and save results
            (Path(tmpdir) / "src").mkdir()
            (Path(tmpdir) / "src" / "main.py").write_text("print('hello')")

            test_results = {"success": True, "passed": 25, "total": 25, "duration": 10.5}
            save_test_results_to_cache(tmpdir, test_results)

            # Check stats after save
            stats_after = get_test_cache_stats(tmpdir)
            assert stats_after["has_cached_results"] == True
            assert stats_after["cache_valid"] == True
            assert stats_after["files_tracked"] == 1
            assert stats_after["last_test_passed"] == 25


class TestCacheManager:
    """Test cache manager functionality."""

    def test_get_stats(self):
        """Test getting comprehensive cache stats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)

            # Create some cached data
            (Path(tmpdir) / "src").mkdir()
            (Path(tmpdir) / "src" / "main.py").write_text("print('hello')")

            save_scout_report_to_cache("Build app", "new_project", tmpdir, "# Scout Report")
            save_test_results_to_cache(tmpdir, {"success": True, "passed": 10, "total": 10, "duration": 5.0})

            # Get stats
            stats = manager.get_stats()

            assert stats["scout_cache"]["total_entries"] == 1
            assert stats["test_cache"]["has_cached_results"] == True
            assert stats["total_files"] > 0

    def test_clear_all(self):
        """Test clearing all cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)

            # Create cached data
            (Path(tmpdir) / "src").mkdir()
            (Path(tmpdir) / "src" / "main.py").write_text("print('hello')")

            save_scout_report_to_cache("Build app", "new_project", tmpdir, "# Scout Report")
            save_test_results_to_cache(tmpdir, {"success": True, "passed": 10, "total": 10, "duration": 5.0})

            # Clear all
            result = manager.clear_all()

            assert result["scout_cache"] == 1
            assert result["test_cache"] == 2  # test-results.json + file-hashes.json
            assert result["total"] == 3

    def test_clear_by_type(self):
        """Test clearing cache by type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)

            # Create cached data
            (Path(tmpdir) / "src").mkdir()
            (Path(tmpdir) / "src" / "main.py").write_text("print('hello')")

            save_scout_report_to_cache("Build app", "new_project", tmpdir, "# Scout Report")
            save_test_results_to_cache(tmpdir, {"success": True, "passed": 10, "total": 10, "duration": 5.0})

            # Clear only scout cache
            deleted = manager.clear_by_type("scout")
            assert deleted == 1

            # Verify scout cache cleared but test cache remains
            stats = manager.get_stats()
            assert stats["scout_cache"]["total_entries"] == 0
            assert stats["test_cache"]["has_cached_results"] == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
