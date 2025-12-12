"""
Unit tests for tools/cache/cache_manager.py

Tests:
- CacheManager.__init__: Initialization and cache directory creation
- get_stats: Cache statistics gathering (empty, scout, test, mixed)
- clean_expired: TTL-based cache cleanup
- clear_all: Full cache clearing
- clear_by_type: Selective cache clearing (scout, test, all, invalid)
- enforce_size_limit: Cache size limit enforcement
- print_stats: Human-readable output
- Integration: Full workflow testing
"""

import pytest
import tempfile
import time
import os
from pathlib import Path
from io import StringIO
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.cache.cache_manager import CacheManager
from tools.cache.scout_cache import save_scout_report_to_cache
from tools.cache.test_cache import save_test_results_to_cache


# Helper Functions


def _create_scout_cache_files(
    tmpdir: str, count: int = 3, size_kb: float = 1.0
) -> None:
    """Create scout cache files with known size."""
    content = "# Scout Report\n" + ("x" * int(size_kb * 1024))
    for i in range(count):
        save_scout_report_to_cache(f"Task {i}", "new_project", tmpdir, content)


def _create_test_cache_files(tmpdir: str, count: int = 3) -> None:
    """Create test cache files."""
    for i in range(count):
        # Create a dummy source file
        (Path(tmpdir) / f"test{i}.py").write_text(f"# Test {i}")
        # Save test results
        save_test_results_to_cache(
            tmpdir, {"success": True, "passed": i + 1, "total": i + 1}
        )


def _create_expired_cache_files(tmpdir: str, count: int = 2) -> None:
    """Create expired cache files by backdating timestamps."""
    cache_dir = Path(tmpdir) / ".context-foundry" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Create old files
    old_time = time.time() - (48 * 3600)  # 48 hours ago
    for i in range(count):
        file_path = cache_dir / f"scout-old-{i}.md"
        file_path.write_text(f"# Old Report {i}")
        os.utime(file_path, (old_time, old_time))


# Test Classes


class TestCacheManagerInit:
    """Test CacheManager initialization."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_init_creates_cache_manager(self):
        """Test that CacheManager initializes correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)

            assert manager.working_directory == tmpdir
            assert manager.cache_dir.exists()
            assert ".context-foundry" in str(manager.cache_dir)
            assert "cache" in str(manager.cache_dir)

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_init_creates_cache_directory(self):
        """Test that cache directory is created on init."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Ensure cache dir doesn't exist initially
            cache_path = Path(tmpdir) / ".context-foundry" / "cache"
            assert not cache_path.exists()

            CacheManager(tmpdir)

            assert cache_path.exists()
            assert cache_path.is_dir()

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_init_with_existing_cache_directory(self):
        """Test initialization with existing cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create cache directory manually
            cache_path = Path(tmpdir) / ".context-foundry" / "cache"
            cache_path.mkdir(parents=True, exist_ok=True)

            # Should not raise error
            manager = CacheManager(tmpdir)

            assert manager.cache_dir == cache_path


class TestGetStats:
    """Test cache statistics gathering."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_get_stats_empty_cache(self):
        """Test get_stats with no cache files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)
            stats = manager.get_stats()

            assert stats["total_files"] == 0
            assert stats["total_size_mb"] == 0
            assert stats["scout_cache"]["total_entries"] == 0
            assert stats["test_cache"]["has_cached_results"] is False

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_get_stats_with_scout_cache(self):
        """Test get_stats counts scout cache files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_scout_cache_files(tmpdir, count=3)

            manager = CacheManager(tmpdir)
            stats = manager.get_stats()

            assert stats["total_files"] > 0
            assert stats["scout_cache"]["total_entries"] == 3
            assert stats["total_size_mb"] > 0

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_get_stats_with_test_cache(self):
        """Test get_stats detects test cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_test_cache_files(tmpdir, count=1)

            manager = CacheManager(tmpdir)
            stats = manager.get_stats()

            assert stats["test_cache"]["has_cached_results"] is True

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_get_stats_with_mixed_cache(self):
        """Test get_stats handles both cache types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_scout_cache_files(tmpdir, count=2)
            _create_test_cache_files(tmpdir, count=1)

            manager = CacheManager(tmpdir)
            stats = manager.get_stats()

            assert stats["scout_cache"]["total_entries"] == 2
            assert stats["test_cache"]["has_cached_results"] is True
            assert stats["total_files"] > 0

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_get_stats_calculates_total_size(self):
        """Test get_stats calculates total size correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with known size (10KB each)
            _create_scout_cache_files(tmpdir, count=3, size_kb=10)

            manager = CacheManager(tmpdir)
            stats = manager.get_stats()

            # Should be at least 0.029 MB (30KB)
            assert stats["total_size_mb"] >= 0.029

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_get_stats_returns_correct_structure(self):
        """Test get_stats returns expected dict structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)
            stats = manager.get_stats()

            # Check all expected keys are present
            assert "cache_dir" in stats
            assert "scout_cache" in stats
            assert "test_cache" in stats
            assert "total_size_mb" in stats
            assert "total_files" in stats
            assert "created_at" in stats


class TestCleanExpired:
    """Test TTL-based cache cleanup."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_clean_expired_removes_old_files(self):
        """Test that expired files are deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create expired files
            _create_expired_cache_files(tmpdir, count=2)

            manager = CacheManager(tmpdir)
            result = manager.clean_expired(ttl_hours=24)

            assert result["total"] > 0

            # Verify files are gone
            cache_dir = Path(tmpdir) / ".context-foundry" / "cache"
            old_files = list(cache_dir.glob("scout-old-*.md"))
            assert len(old_files) == 0

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_clean_expired_preserves_recent_files(self):
        """Test that valid files are not deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create recent files
            _create_scout_cache_files(tmpdir, count=3)

            manager = CacheManager(tmpdir)
            result = manager.clean_expired(ttl_hours=24)

            # No files should be deleted
            assert result["total"] == 0

            # Verify files still exist
            stats = manager.get_stats()
            assert stats["scout_cache"]["total_entries"] == 3

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_clean_expired_empty_cache(self):
        """Test clean_expired handles empty cache gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)
            result = manager.clean_expired()

            assert result["total"] == 0
            assert result["scout_cache"] == 0
            assert result["test_cache"] == 0

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_clean_expired_categorizes_deletions(self):
        """Test that deletions are categorized by type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create both scout and test cache files
            _create_scout_cache_files(tmpdir, count=2)
            _create_test_cache_files(tmpdir, count=1)

            manager = CacheManager(tmpdir)
            # Use ttl_hours=0 to expire all files immediately
            result = manager.clean_expired(ttl_hours=0)

            # Both types should have deletions
            assert result["total"] > 0
            assert "scout_cache" in result
            assert "test_cache" in result

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_clean_expired_custom_ttl(self):
        """Test clean_expired with custom TTL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create expired files
            _create_expired_cache_files(tmpdir, count=2)

            manager = CacheManager(tmpdir)

            # With large TTL, files should not be deleted
            result_large_ttl = manager.clean_expired(ttl_hours=1000)
            assert result_large_ttl["total"] == 0

            # With small TTL, files should be deleted
            result_small_ttl = manager.clean_expired(ttl_hours=1)
            assert result_small_ttl["total"] > 0


class TestClearAll:
    """Test full cache clearing."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_clear_all_removes_all_cache_files(self):
        """Test that clear_all removes all cache files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create both types of cache
            _create_scout_cache_files(tmpdir, count=3)
            _create_test_cache_files(tmpdir, count=2)

            manager = CacheManager(tmpdir)
            result = manager.clear_all()

            assert result["total"] > 0

            # Verify all files are gone
            stats = manager.get_stats()
            assert stats["total_files"] == 0

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_clear_all_returns_correct_counts(self):
        """Test that clear_all returns accurate deletion counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_scout_cache_files(tmpdir, count=3)
            _create_test_cache_files(tmpdir, count=2)

            manager = CacheManager(tmpdir)
            result = manager.clear_all()

            assert result["scout_cache"] == 3
            assert result["test_cache"] >= 1
            assert result["total"] >= 4

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_clear_all_empty_cache(self):
        """Test clear_all handles empty cache gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)
            result = manager.clear_all()

            assert result["total"] == 0


class TestClearByType:
    """Test selective cache clearing."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_clear_by_type_scout(self):
        """Test clearing only scout cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_scout_cache_files(tmpdir, count=3)
            _create_test_cache_files(tmpdir, count=2)

            manager = CacheManager(tmpdir)
            count = manager.clear_by_type("scout")

            assert count == 3

            # Verify only scout files deleted
            stats = manager.get_stats()
            assert stats["scout_cache"]["total_entries"] == 0
            assert stats["test_cache"]["has_cached_results"] is True

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_clear_by_type_test(self):
        """Test clearing only test cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_scout_cache_files(tmpdir, count=3)
            _create_test_cache_files(tmpdir, count=2)

            manager = CacheManager(tmpdir)
            count = manager.clear_by_type("test")

            assert count >= 1

            # Verify only test files deleted
            stats = manager.get_stats()
            assert stats["scout_cache"]["total_entries"] == 3
            assert stats["test_cache"]["has_cached_results"] is False

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_clear_by_type_all(self):
        """Test that 'all' type clears everything."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_scout_cache_files(tmpdir, count=3)
            _create_test_cache_files(tmpdir, count=2)

            manager = CacheManager(tmpdir)
            count = manager.clear_by_type("all")

            assert count > 0

            # Verify all files deleted
            stats = manager.get_stats()
            assert stats["total_files"] == 0

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_clear_by_type_invalid_raises_error(self):
        """Test that invalid type raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)

            with pytest.raises(ValueError) as exc_info:
                manager.clear_by_type("invalid")

            assert "Unknown cache type" in str(exc_info.value)

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_clear_by_type_empty_cache(self):
        """Test clear_by_type handles empty cache for all types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)

            # Test all valid types
            assert manager.clear_by_type("scout") == 0
            assert manager.clear_by_type("test") == 0
            assert manager.clear_by_type("all") == 0


class TestEnforceSizeLimit:
    """Test cache size limit enforcement."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_enforce_size_limit_under_limit(self):
        """Test no deletion when under limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 0.5MB cache
            _create_scout_cache_files(tmpdir, count=50, size_kb=10)

            manager = CacheManager(tmpdir)
            result = manager.enforce_size_limit(max_size_mb=1)

            assert result["deleted_files"] == 0
            assert result["freed_mb"] == 0

            # All files should remain
            stats = manager.get_stats()
            assert stats["scout_cache"]["total_entries"] == 50

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_enforce_size_limit_over_limit(self):
        """Test deletion when over limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 2MB cache
            _create_scout_cache_files(tmpdir, count=200, size_kb=10)

            manager = CacheManager(tmpdir)
            result = manager.enforce_size_limit(max_size_mb=1)

            assert result["deleted_files"] > 0
            assert result["freed_mb"] > 0
            assert result["current_size_mb"] <= 1

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_enforce_size_limit_deletes_oldest_first(self):
        """Test that oldest files are deleted first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / ".context-foundry" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Create files with staggered timestamps
            now = time.time()
            files = []
            for i in range(5):
                file_path = cache_dir / f"scout-test-{i}.md"
                content = "x" * (200 * 1024)  # 200KB each = 1MB total
                file_path.write_text(content)

                # Backdate files (oldest to newest)
                file_time = now - ((4 - i) * 3600)  # Hours ago
                os.utime(file_path, (file_time, file_time))
                files.append(file_path)

            manager = CacheManager(tmpdir)
            manager.enforce_size_limit(max_size_mb=0.5)

            # Oldest files should be deleted
            assert not files[0].exists()
            assert not files[1].exists()
            # Newest files should remain
            assert files[4].exists()

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_enforce_size_limit_exact_limit(self):
        """Test behavior at exact limit boundary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create cache close to 1MB
            _create_scout_cache_files(tmpdir, count=100, size_kb=10)

            manager = CacheManager(tmpdir)
            stats_before = manager.get_stats()

            # Add a small buffer to handle rounding (metadata overhead)
            result = manager.enforce_size_limit(
                max_size_mb=stats_before["total_size_mb"] + 0.1
            )

            # Should not delete any files when given slightly more than current size
            assert result["deleted_files"] == 0

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_enforce_size_limit_empty_cache(self):
        """Test enforce_size_limit handles empty cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)
            result = manager.enforce_size_limit()

            assert result["deleted_files"] == 0
            assert result["current_size_mb"] == 0

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_enforce_size_limit_deletes_correct_count(self):
        """Test that minimum necessary files are deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 10 files of 100KB each = 1MB total
            _create_scout_cache_files(tmpdir, count=10, size_kb=100)

            manager = CacheManager(tmpdir)
            # Set limit to 0.5MB, should delete approximately half
            result = manager.enforce_size_limit(max_size_mb=0.5)

            assert result["deleted_files"] >= 4
            assert result["current_size_mb"] <= 0.5

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_enforce_size_limit_zero_limit(self):
        """Test that zero limit deletes all files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_scout_cache_files(tmpdir, count=5)

            manager = CacheManager(tmpdir)
            result = manager.enforce_size_limit(max_size_mb=0)

            # All files should be deleted
            assert result["deleted_files"] >= 5
            stats = manager.get_stats()
            assert stats["total_files"] == 0

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_enforce_size_limit_returns_correct_structure(self):
        """Test result dict has expected keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)
            result = manager.enforce_size_limit()

            assert "deleted_files" in result
            assert "freed_mb" in result
            assert "current_size_mb" in result


class TestPrintStats:
    """Test human-readable stats output."""

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_print_stats_runs_without_error(self):
        """Test print_stats doesn't crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_scout_cache_files(tmpdir, count=2)

            manager = CacheManager(tmpdir)

            # Should not raise exception
            try:
                # Redirect stdout to prevent cluttering test output
                old_stdout = sys.stdout
                sys.stdout = StringIO()

                manager.print_stats()

                sys.stdout = old_stdout
            except Exception as e:
                sys.stdout = old_stdout
                pytest.fail(f"print_stats raised exception: {e}")

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_print_stats_output_contains_expected_sections(self):
        """Test print_stats output contains expected content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_scout_cache_files(tmpdir, count=2)
            _create_test_cache_files(tmpdir, count=1)

            manager = CacheManager(tmpdir)

            # Capture output
            old_stdout = sys.stdout
            sys.stdout = StringIO()

            manager.print_stats()

            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

            # Check for expected sections
            assert "Cache Statistics" in output
            assert "Scout Cache" in output
            assert "Test Cache" in output
            assert "Total size" in output
            assert "Total files" in output


class TestCacheManagerIntegration:
    """Integration tests for CacheManager workflows."""

    @pytest.mark.integration
    @pytest.mark.tier2
    def test_full_workflow_create_stats_clear(self):
        """Test complete workflow: create → stats → clear."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)

            # Step 1: Create cache files
            _create_scout_cache_files(tmpdir, count=3)
            _create_test_cache_files(tmpdir, count=2)

            # Step 2: Get stats
            stats_full = manager.get_stats()
            assert stats_full["scout_cache"]["total_entries"] == 3
            assert stats_full["test_cache"]["has_cached_results"] is True

            # Step 3: Clear all
            result = manager.clear_all()
            assert result["total"] > 0

            # Step 4: Verify empty
            stats_empty = manager.get_stats()
            assert stats_empty["total_files"] == 0

    @pytest.mark.integration
    @pytest.mark.tier2
    def test_workflow_with_size_limit_enforcement(self):
        """Test size limit enforcement workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)

            # Create large cache
            _create_scout_cache_files(tmpdir, count=100, size_kb=10)

            # Check size before
            stats_before = manager.get_stats()
            size_before = stats_before["total_size_mb"]

            # Enforce size limit
            result = manager.enforce_size_limit(max_size_mb=0.5)

            # Verify size reduced
            assert result["current_size_mb"] <= 0.5
            assert result["freed_mb"] > 0

            # Verify stats show reduced size
            stats_after = manager.get_stats()
            assert stats_after["total_size_mb"] < size_before

    @pytest.mark.integration
    @pytest.mark.tier2
    def test_workflow_with_ttl_cleanup(self):
        """Test TTL cleanup workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)

            # Create old and new files
            _create_expired_cache_files(tmpdir, count=3)
            _create_scout_cache_files(tmpdir, count=2)

            # Stats before cleanup
            stats_before = manager.get_stats()
            files_before = stats_before["total_files"]

            # Clean expired
            result = manager.clean_expired(ttl_hours=24)

            # Verify only old files removed
            assert result["total"] == 3

            # Stats should show reduced count
            stats_after = manager.get_stats()
            assert stats_after["total_files"] < files_before
            assert stats_after["scout_cache"]["total_entries"] == 2

    @pytest.mark.integration
    @pytest.mark.tier2
    def test_mixed_cache_operations(self):
        """Test mixed cache operations work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)

            # Create both types
            _create_scout_cache_files(tmpdir, count=3)
            _create_test_cache_files(tmpdir, count=2)

            # Clear scout only
            scout_count = manager.clear_by_type("scout")
            assert scout_count == 3

            # Verify test remains
            stats = manager.get_stats()
            assert stats["scout_cache"]["total_entries"] == 0
            assert stats["test_cache"]["has_cached_results"] is True

            # Clear test only
            test_count = manager.clear_by_type("test")
            assert test_count >= 1

            # Verify all gone
            stats_final = manager.get_stats()
            assert stats_final["total_files"] == 0

    @pytest.mark.integration
    @pytest.mark.tier2
    def test_repeated_operations_stable(self):
        """Test repeated operations don't cause issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CacheManager(tmpdir)

            # Repeat operations 10 times
            for i in range(10):
                # Create cache
                _create_scout_cache_files(tmpdir, count=2)

                # Get stats
                stats = manager.get_stats()
                assert stats["scout_cache"]["total_entries"] >= 2

                # Clear
                result = manager.clear_all()
                assert result["scout_cache"] >= 2

                # Verify empty
                stats_empty = manager.get_stats()
                assert stats_empty["total_files"] == 0
