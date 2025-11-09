"""
Unit tests for tools/cache/scout_cache.py

Tests:
- normalize_task_description: Task normalization for cache matching
- generate_scout_cache_key: Cache key generation consistency
- get_cached_scout_report: Cache hit/miss logic
- save_scout_report_to_cache: Report persistence
- clear_scout_cache: Cache cleanup
- get_scout_cache_stats: Cache statistics
"""

import pytest
import tempfile
from pathlib import Path

# Import scout cache module
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.cache.scout_cache import (
    normalize_task_description,
    generate_scout_cache_key,
    get_cached_scout_report,
    save_scout_report_to_cache,
    clear_scout_cache,
    get_scout_cache_stats,
)


class TestNormalizeTaskDescription:
    """Test task normalization for better cache matching."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_normalize_removes_extra_whitespace(self):
        """Test that extra whitespace is removed."""
        task = "Build  a   weather    app"
        result = normalize_task_description(task)
        assert "  " not in result
        assert result == "build a weather app"

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_normalize_converts_to_lowercase(self):
        """Test that uppercase is converted to lowercase."""
        task = "BUILD A WEATHER APP"
        result = normalize_task_description(task)
        assert result == "build a weather app"

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_normalize_consistent_for_similar_tasks(self):
        """Test that similar tasks normalize to same string."""
        task1 = "Build a weather app"
        task2 = "Build  a   weather    app"
        task3 = "BUILD A WEATHER APP"

        assert normalize_task_description(task1) == normalize_task_description(task2)
        assert normalize_task_description(task1) == normalize_task_description(task3)

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_normalize_empty_string(self):
        """Test normalizing empty string."""
        result = normalize_task_description("")
        assert result == ""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_normalize_preserves_meaning(self):
        """Test that normalization preserves task meaning."""
        task = "Create React TODO app with TypeScript"
        result = normalize_task_description(task)
        assert "react" in result
        assert "todo" in result
        assert "typescript" in result


class TestGenerateCacheKey:
    """Test cache key generation consistency."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_same_inputs_generate_same_key(self):
        """Test that same inputs produce same cache key."""
        key1 = generate_scout_cache_key("Build TODO app", "new_project", "/tmp/project")
        key2 = generate_scout_cache_key("Build TODO app", "new_project", "/tmp/project")
        assert key1 == key2

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_different_tasks_generate_different_keys(self):
        """Test that different tasks produce different keys."""
        key1 = generate_scout_cache_key("Build TODO app", "new_project", "/tmp/project")
        key2 = generate_scout_cache_key(
            "Build weather app", "new_project", "/tmp/project"
        )
        assert key1 != key2

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_different_modes_generate_different_keys(self):
        """Test that different modes produce different keys."""
        key1 = generate_scout_cache_key("Build app", "new_project", "/tmp/project")
        key2 = generate_scout_cache_key("Build app", "add_feature", "/tmp/project")
        assert key1 != key2

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_cache_key_is_string(self):
        """Test that cache key is a string."""
        key = generate_scout_cache_key("Build app", "new_project", "/tmp/project")
        assert isinstance(key, str)
        assert len(key) > 0

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_normalized_tasks_generate_same_key(self):
        """Test that variations of same task generate same key."""
        key1 = generate_scout_cache_key(
            "Build weather app", "new_project", "/tmp/project"
        )
        key2 = generate_scout_cache_key(
            "BUILD  WEATHER   APP", "new_project", "/tmp/project"
        )
        assert key1 == key2  # Should be same due to normalization


class TestScoutCacheHitMiss:
    """Test cache hit/miss scenarios."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_cache_miss_no_prior_save(self):
        """Test cache miss when nothing saved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cached = get_cached_scout_report("Build app", "new_project", tmpdir)
            assert cached is None

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_cache_hit_after_save(self):
        """Test cache hit after saving report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = "Build test app"
            mode = "new_project"
            report = "# Scout Report\nTest content"

            # Save report
            save_scout_report_to_cache(task, mode, tmpdir, report)

            # Retrieve report
            cached = get_cached_scout_report(task, mode, tmpdir)
            assert cached == report

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_cache_miss_different_task(self):
        """Test cache miss for different task."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task1 = "Build app A"
            task2 = "Build app B"
            mode = "new_project"
            report = "# Scout Report"

            # Save for task1
            save_scout_report_to_cache(task1, mode, tmpdir, report)

            # Try to retrieve for task2
            cached = get_cached_scout_report(task2, mode, tmpdir)
            assert cached is None

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_cache_miss_different_mode(self):
        """Test cache miss for different mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = "Build app"
            mode1 = "new_project"
            mode2 = "add_feature"
            report = "# Scout Report"

            # Save for mode1
            save_scout_report_to_cache(task, mode1, tmpdir, report)

            # Try to retrieve for mode2
            cached = get_cached_scout_report(task, mode2, tmpdir)
            assert cached is None

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_cache_hit_similar_task_phrasing(self):
        """Test cache hit for similar task phrasing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task1 = "Build weather app"
            task2 = "BUILD  WEATHER   APP"  # Different case/spacing
            mode = "new_project"
            report = "# Scout Report"

            # Save for task1
            save_scout_report_to_cache(task1, mode, tmpdir, report)

            # Retrieve for task2 (should hit due to normalization)
            cached = get_cached_scout_report(task2, mode, tmpdir)
            assert cached == report


class TestScoutCacheTTL:
    """Test cache expiration logic."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_cache_valid_within_ttl(self):
        """Test that cache is valid within TTL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = "Build app"
            mode = "new_project"
            report = "# Scout Report"

            # Save report
            save_scout_report_to_cache(task, mode, tmpdir, report)

            # Retrieve immediately (within TTL)
            cached = get_cached_scout_report(task, mode, tmpdir, ttl_hours=24)
            assert cached == report

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_cache_custom_ttl(self):
        """Test cache with custom TTL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = "Build app"
            mode = "new_project"
            report = "# Scout Report"

            # Save report
            save_scout_report_to_cache(task, mode, tmpdir, report)

            # Should be valid with large TTL
            cached = get_cached_scout_report(task, mode, tmpdir, ttl_hours=1000)
            assert cached == report


class TestSaveScoutReport:
    """Test report persistence."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_save_creates_cache_file(self):
        """Test that saving creates cache file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = "Build app"
            mode = "new_project"
            report = "# Scout Report\nContent"

            save_scout_report_to_cache(task, mode, tmpdir, report)

            # Check that cache directory was created
            cache_dir = Path(tmpdir) / ".context-foundry" / "cache"
            assert cache_dir.exists()

            # Check that a scout cache file exists
            scout_files = list(cache_dir.glob("scout-*.md"))
            assert len(scout_files) > 0

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_save_persists_correct_content(self):
        """Test that saved content can be retrieved exactly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = "Build app"
            mode = "new_project"
            report = "# Scout Report\n\nDetailed content\n\nMore sections"

            save_scout_report_to_cache(task, mode, tmpdir, report)
            cached = get_cached_scout_report(task, mode, tmpdir)

            assert cached == report

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_save_overwrites_existing(self):
        """Test that saving overwrites existing cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = "Build app"
            mode = "new_project"
            report1 = "# Scout Report v1"
            report2 = "# Scout Report v2"

            # Save first version
            save_scout_report_to_cache(task, mode, tmpdir, report1)

            # Save second version (should overwrite)
            save_scout_report_to_cache(task, mode, tmpdir, report2)

            # Should get second version
            cached = get_cached_scout_report(task, mode, tmpdir)
            assert cached == report2


class TestClearScoutCache:
    """Test cache cleanup."""

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_clear_removes_all_cache_files(self):
        """Test that clear removes all scout cache files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save multiple reports
            for i in range(3):
                save_scout_report_to_cache(
                    f"Build app {i}", "new_project", tmpdir, f"# Report {i}"
                )

            # Clear cache
            deleted = clear_scout_cache(tmpdir)
            assert deleted == 3

            # Verify all cleared
            cache_dir = Path(tmpdir) / ".context-foundry" / "cache"
            scout_files = list(cache_dir.glob("scout-*.md"))
            assert len(scout_files) == 0

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_clear_empty_cache_returns_zero(self):
        """Test that clearing empty cache returns 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            deleted = clear_scout_cache(tmpdir)
            assert deleted == 0


class TestScoutCacheStats:
    """Test cache statistics."""

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_stats_empty_cache(self):
        """Test stats for empty cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats = get_scout_cache_stats(tmpdir)
            assert stats["total_entries"] == 0
            assert stats["valid_entries"] == 0
            assert stats["expired_entries"] == 0
            assert stats["total_size_kb"] == 0

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_stats_with_cached_reports(self):
        """Test stats with cached reports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save some reports
            for i in range(3):
                save_scout_report_to_cache(
                    f"Build app {i}",
                    "new_project",
                    tmpdir,
                    f"# Report {i}" * 100,  # Make it reasonably sized
                )

            stats = get_scout_cache_stats(tmpdir)
            assert stats["total_entries"] == 3
            assert stats["valid_entries"] == 3
            assert stats["total_size_kb"] > 0

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_stats_counts_size_correctly(self):
        """Test that stats calculates total size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save a report with known size
            large_report = "# Scout Report\n" + ("x" * 10000)  # ~10KB
            save_scout_report_to_cache("Build app", "new_project", tmpdir, large_report)

            stats = get_scout_cache_stats(tmpdir)
            assert stats["total_size_kb"] > 9  # Should be at least 9KB


class TestScoutCacheIntegration:
    """Integration tests for scout cache."""

    @pytest.mark.integration
    @pytest.mark.tier2
    def test_multiple_tasks_independent_caching(self):
        """Test that multiple tasks cache independently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks = [
                ("Build TODO app", "# TODO Report"),
                ("Build weather app", "# Weather Report"),
                ("Build blog", "# Blog Report"),
            ]

            mode = "new_project"

            # Save all reports
            for task, report in tasks:
                save_scout_report_to_cache(task, mode, tmpdir, report)

            # Verify each can be retrieved correctly
            for task, expected_report in tasks:
                cached = get_cached_scout_report(task, mode, tmpdir)
                assert cached == expected_report

    @pytest.mark.integration
    @pytest.mark.tier2
    def test_save_retrieve_clear_workflow(self):
        """Test full workflow: save → retrieve → clear."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = "Build app"
            mode = "new_project"
            report = "# Scout Report"

            # Save
            save_scout_report_to_cache(task, mode, tmpdir, report)

            # Retrieve
            cached = get_cached_scout_report(task, mode, tmpdir)
            assert cached == report

            # Check stats
            stats = get_scout_cache_stats(tmpdir)
            assert stats["total_entries"] == 1

            # Clear
            deleted = clear_scout_cache(tmpdir)
            assert deleted == 1

            # Verify cleared
            cached_after_clear = get_cached_scout_report(task, mode, tmpdir)
            assert cached_after_clear is None

            # Stats should be empty
            stats_after = get_scout_cache_stats(tmpdir)
            assert stats_after["total_entries"] == 0
