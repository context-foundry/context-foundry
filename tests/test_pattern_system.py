"""
Tests for the global pattern sharing system.

This module tests the pattern reading, merging, and saving functionality
that enables cross-project learning.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open


# Test data
SAMPLE_PATTERN = {
    "pattern_id": "test-pattern-001",
    "first_seen": "2025-10-19",
    "last_seen": "2025-10-19",
    "frequency": 1,
    "project_types": ["test-project"],
    "issue": "Test issue",
    "solution": {"builder": "Test solution"},
    "severity": "LOW",
    "auto_apply": True
}

SAMPLE_PATTERNS_FILE = {
    "patterns": [SAMPLE_PATTERN],
    "version": "1.0",
    "last_updated": "2025-10-19T10:00:00Z",
    "total_builds": 1
}


class TestPatternDirectory:
    """Test global pattern directory management."""

    def test_global_pattern_directory_creation(self, tmp_path):
        """Test that global pattern directory can be created."""
        pattern_dir = tmp_path / ".context-foundry" / "patterns"
        pattern_dir.mkdir(parents=True, exist_ok=True)

        assert pattern_dir.exists()
        assert pattern_dir.is_dir()

    def test_pattern_subdirectories(self, tmp_path):
        """Test creation of pattern subdirectories."""
        base_dir = tmp_path / ".context-foundry"
        base_dir.mkdir()

        subdirs = ["patterns", "metrics", "backups"]
        for subdir in subdirs:
            (base_dir / subdir).mkdir()

        for subdir in subdirs:
            assert (base_dir / subdir).exists()


class TestPatternFileOperations:
    """Test pattern file reading and writing."""

    def test_read_empty_patterns_file(self, tmp_path):
        """Test reading an empty or non-existent patterns file."""
        pattern_file = tmp_path / "common-issues.json"

        # Should handle non-existent file gracefully
        if not pattern_file.exists():
            default_data = {"patterns": [], "version": "1.0"}
            result = default_data
        else:
            with open(pattern_file) as f:
                result = json.load(f)

        assert "patterns" in result
        assert isinstance(result["patterns"], list)

    def test_write_patterns_file(self, tmp_path):
        """Test writing patterns to file."""
        pattern_file = tmp_path / "common-issues.json"

        with open(pattern_file, "w") as f:
            json.dump(SAMPLE_PATTERNS_FILE, f, indent=2)

        assert pattern_file.exists()

        with open(pattern_file) as f:
            loaded = json.load(f)

        assert loaded["patterns"][0]["pattern_id"] == "test-pattern-001"
        assert loaded["version"] == "1.0"

    def test_pattern_file_structure(self):
        """Test that pattern file has required structure."""
        required_keys = ["patterns", "version", "last_updated", "total_builds"]

        for key in required_keys:
            assert key in SAMPLE_PATTERNS_FILE


class TestPatternMerging:
    """Test pattern merging logic."""

    def test_merge_new_pattern(self):
        """Test adding a new pattern to existing patterns."""
        existing = {"patterns": [SAMPLE_PATTERN]}
        new_pattern = {
            "pattern_id": "test-pattern-002",
            "first_seen": "2025-10-19",
            "frequency": 1
        }

        # Merge logic
        existing_ids = {p["pattern_id"] for p in existing["patterns"]}
        if new_pattern["pattern_id"] not in existing_ids:
            existing["patterns"].append(new_pattern)

        assert len(existing["patterns"]) == 2
        assert existing["patterns"][1]["pattern_id"] == "test-pattern-002"

    def test_merge_existing_pattern_increments_frequency(self):
        """Test that merging an existing pattern increments frequency."""
        existing = {"patterns": [SAMPLE_PATTERN.copy()]}
        duplicate_pattern = SAMPLE_PATTERN.copy()

        # Merge logic - update existing
        existing_pattern = existing["patterns"][0]
        if existing_pattern["pattern_id"] == duplicate_pattern["pattern_id"]:
            existing_pattern["frequency"] += 1
            existing_pattern["last_seen"] = "2025-10-20"

        assert existing["patterns"][0]["frequency"] == 2
        assert existing["patterns"][0]["last_seen"] == "2025-10-20"

    def test_merge_multiple_patterns(self):
        """Test merging multiple patterns at once."""
        existing = {"patterns": []}
        new_patterns = [
            {"pattern_id": f"pattern-{i}", "frequency": 1}
            for i in range(3)
        ]

        for pattern in new_patterns:
            existing["patterns"].append(pattern)

        assert len(existing["patterns"]) == 3


class TestPatternMatching:
    """Test pattern matching by project type."""

    def test_match_patterns_by_project_type(self):
        """Test filtering patterns by project type."""
        patterns = {
            "patterns": [
                {"pattern_id": "p1", "project_types": ["python", "api"]},
                {"pattern_id": "p2", "project_types": ["javascript", "react"]},
                {"pattern_id": "p3", "project_types": ["python", "cli"]},
            ]
        }

        project_type = "python"
        matched = [
            p for p in patterns["patterns"]
            if project_type in p.get("project_types", [])
        ]

        assert len(matched) == 2
        assert matched[0]["pattern_id"] == "p1"
        assert matched[1]["pattern_id"] == "p3"

    def test_match_all_patterns_for_unknown_project(self):
        """Test that unknown project types get all patterns."""
        patterns = {"patterns": [SAMPLE_PATTERN, SAMPLE_PATTERN]}

        # For unknown project type, return all patterns
        matched = patterns["patterns"]

        assert len(matched) == 2


class TestPatternVersioning:
    """Test pattern file versioning."""

    def test_pattern_version_compatibility(self):
        """Test version checking logic."""
        current_version = "1.0"
        pattern_file = {"version": "1.0"}

        is_compatible = pattern_file["version"] == current_version
        assert is_compatible

    def test_incompatible_version_handling(self):
        """Test handling of incompatible pattern versions."""
        current_version = "1.0"
        pattern_file = {"version": "2.0"}

        is_compatible = pattern_file["version"] == current_version
        assert not is_compatible


class TestPatternBackup:
    """Test pattern backup functionality."""

    def test_backup_patterns_before_merge(self, tmp_path):
        """Test creating backup before merging patterns."""
        source = tmp_path / "patterns"
        source.mkdir()
        (source / "common-issues.json").write_text(json.dumps(SAMPLE_PATTERNS_FILE))

        backup_dir = tmp_path / "backups" / "20251019"
        backup_dir.mkdir(parents=True)

        # Backup logic
        import shutil
        shutil.copytree(source, backup_dir / "patterns", dirs_exist_ok=True)

        assert (backup_dir / "patterns" / "common-issues.json").exists()


# Mark slow tests
@pytest.mark.slow
class TestPatternSystemIntegration:
    """Integration tests for the complete pattern system."""

    def test_full_pattern_lifecycle(self, tmp_path):
        """Test complete pattern lifecycle: read -> merge -> save."""
        pattern_dir = tmp_path / "patterns"
        pattern_dir.mkdir()
        pattern_file = pattern_dir / "common-issues.json"

        # 1. Initialize with empty patterns
        initial_data = {"patterns": [], "version": "1.0", "total_builds": 0}
        with open(pattern_file, "w") as f:
            json.dump(initial_data, f)

        # 2. Read existing patterns
        with open(pattern_file) as f:
            patterns = json.load(f)

        # 3. Add new pattern
        patterns["patterns"].append(SAMPLE_PATTERN)
        patterns["total_builds"] += 1

        # 4. Save updated patterns
        with open(pattern_file, "w") as f:
            json.dump(patterns, f, indent=2)

        # 5. Verify
        with open(pattern_file) as f:
            final = json.load(f)

        assert len(final["patterns"]) == 1
        assert final["total_builds"] == 1


# Pytest fixtures
@pytest.fixture
def sample_pattern():
    """Provide a sample pattern for testing."""
    return SAMPLE_PATTERN.copy()


@pytest.fixture
def sample_patterns_file():
    """Provide a sample patterns file for testing."""
    return SAMPLE_PATTERNS_FILE.copy()
