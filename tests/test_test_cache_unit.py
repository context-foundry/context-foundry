"""
Unit tests for tools/cache/test_cache.py

Tests:
- hash_file: File content hashing
- compute_file_hashes: Batch file hashing
- get_cached_test_results: Cache hit/miss for test results
- save_test_results_to_cache: Test result persistence
- Test result caching prevents redundant test execution
"""

import pytest
import tempfile
from pathlib import Path
import json

# Import test cache module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.cache.test_cache import (
    hash_file,
    compute_file_hashes,
    get_cached_test_results,
    save_test_results_to_cache,
    clear_test_cache,
    get_test_cache_stats
)


class TestFileHashing:
    """Test file content hashing."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_hash_file_consistent(self):
        """Test that same file produces same hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("test content")
            
            hash1 = hash_file(file_path)
            hash2 = hash_file(file_path)
            
            assert hash1 == hash2
            assert isinstance(hash1, str)
            assert len(hash1) > 0

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_hash_file_different_content_different_hash(self):
        """Test that different content produces different hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "test1.txt"
            file2 = Path(tmpdir) / "test2.txt"
            
            file1.write_text("content A")
            file2.write_text("content B")
            
            hash1 = hash_file(file1)
            hash2 = hash_file(file2)
            
            assert hash1 != hash2

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_hash_file_changed_content_different_hash(self):
        """Test that modifying file changes hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            
            file_path.write_text("original")
            hash1 = hash_file(file_path)
            
            file_path.write_text("modified")
            hash2 = hash_file(file_path)
            
            assert hash1 != hash2

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_hash_file_nonexistent_returns_empty(self):
        """Test that nonexistent file returns empty string."""
        result = hash_file(Path("/nonexistent/file.txt"))
        assert result == ""


class TestComputeFileHashes:
    """Test batch file hashing."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_compute_multiple_files(self):
        """Test computing hashes for multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files with source extensions (.py)
            for i in range(3):
                (Path(tmpdir) / f"test{i}.py").write_text(f"# content {i}")

            hashes = compute_file_hashes(tmpdir)

            # Should have 3 entries
            assert len(hashes) == 3

            # All should be non-empty
            for file_path, hash_val in hashes.items():
                assert hash_val != ""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_compute_empty_directory(self):
        """Test computing hashes for empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hashes = compute_file_hashes(tmpdir)
            assert len(hashes) == 0


class TestCacheHitMiss:
    """Test cache hit/miss for test results."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_cache_miss_no_prior_run(self):
        """Test cache miss when no previous run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_cached_test_results(tmpdir)
            assert result is None

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_cache_hit_after_save(self):
        """Test cache hit after saving results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_results = {
                "success": True,
                "passed": 10,
                "total": 10,
                "duration": 1.5
            }
            
            # Create a dummy file to hash
            (Path(tmpdir) / "test.py").write_text("test code")
            
            # Save results
            save_test_results_to_cache(tmpdir, test_results)
            
            # Should get cache hit
            cached = get_cached_test_results(tmpdir)
            assert cached is not None
            assert cached["passed"] == 10

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_cache_miss_after_file_change(self):
        """Test cache miss after file is modified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("original code")
            
            test_results = {
                "success": True,
                "passed": 10,
                "total": 10
            }
            
            # Save results with original file
            save_test_results_to_cache(tmpdir, test_results)
            
            # Modify file
            test_file.write_text("modified code")
            
            # Should get cache miss
            cached = get_cached_test_results(tmpdir)
            assert cached is None

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_cache_hit_no_changes(self):
        """Test cache hit when files unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            (Path(tmpdir) / "test1.py").write_text("test code 1")
            (Path(tmpdir) / "test2.py").write_text("test code 2")
            
            test_results = {
                "success": True,
                "passed": 15,
                "total": 15,
                "duration": 2.0
            }
            
            # Save results
            save_test_results_to_cache(tmpdir, test_results)
            
            # Get cached (files unchanged)
            cached = get_cached_test_results(tmpdir)
            assert cached is not None
            assert cached["passed"] == 15
            assert cached["total"] == 15


class TestSaveTestResults:
    """Test result persistence."""

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_save_creates_cache_file(self):
        """Test that save creates cache files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.py").write_text("test code")
            
            test_results = {
                "success": True,
                "passed": 5,
                "total": 5
            }
            
            save_test_results_to_cache(tmpdir, test_results)
            
            # Check cache directory exists
            cache_dir = Path(tmpdir) / ".context-foundry" / "cache"
            assert cache_dir.exists()

    @pytest.mark.unit
    @pytest.mark.tier1
    def test_save_overwrites_previous(self):
        """Test that new save overwrites previous."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.py").write_text("test code")
            
            # Save first results
            save_test_results_to_cache(tmpdir, {
                "success": True,
                "passed": 5,
                "total": 5
            })
            
            # Save second results
            save_test_results_to_cache(tmpdir, {
                "success": True,
                "passed": 10,
                "total": 10
            })
            
            # Should get second results
            cached = get_cached_test_results(tmpdir)
            assert cached["passed"] == 10


class TestClearTestCache:
    """Test cache cleanup."""

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_clear_removes_cache(self):
        """Test that clear removes test cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.py").write_text("test code")
            
            # Save results
            save_test_results_to_cache(tmpdir, {
                "success": True,
                "passed": 5,
                "total": 5
            })
            
            # Clear cache
            deleted = clear_test_cache(tmpdir)
            assert deleted >= 0
            
            # Should get cache miss after clear
            cached = get_cached_test_results(tmpdir)
            assert cached is None


class TestTestCacheStats:
    """Test cache statistics."""

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_stats_empty_cache(self):
        """Test stats for empty cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats = get_test_cache_stats(tmpdir)
            assert isinstance(stats, dict)

    @pytest.mark.unit
    @pytest.mark.tier2
    def test_stats_with_cache(self):
        """Test stats with cached results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.py").write_text("test code")
            
            save_test_results_to_cache(tmpdir, {
                "success": True,
                "passed": 5,
                "total": 5
            })
            
            stats = get_test_cache_stats(tmpdir)
            assert isinstance(stats, dict)


class TestTestCacheIntegration:
    """Integration tests for test cache."""

    @pytest.mark.integration
    @pytest.mark.tier2
    def test_full_workflow_cache_hit(self):
        """Test full workflow: save → no changes → cache hit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def test_example(): pass")
            
            # Save test results
            results = {
                "success": True,
                "passed": 10,
                "total": 10,
                "duration": 1.5
            }
            save_test_results_to_cache(tmpdir, results)
            
            # Get cached results (should hit)
            cached = get_cached_test_results(tmpdir)
            assert cached is not None
            assert cached["passed"] == 10
            
            # Verify file unchanged
            assert test_file.read_text() == "def test_example(): pass"

    @pytest.mark.integration
    @pytest.mark.tier2
    def test_full_workflow_cache_miss_after_change(self):
        """Test full workflow: save → change file → cache miss."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def test_v1(): pass")
            
            # Save results for v1
            save_test_results_to_cache(tmpdir, {
                "success": True,
                "passed": 5,
                "total": 5
            })
            
            # Modify file (v2)
            test_file.write_text("def test_v2(): pass")
            
            # Should get cache miss
            cached = get_cached_test_results(tmpdir)
            assert cached is None
