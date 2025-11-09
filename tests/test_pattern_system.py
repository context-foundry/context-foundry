"""
Tests for the global pattern sharing system.

This module tests the pattern reading, merging, and saving functionality
that enables cross-project learning.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys


# Mock FastMCP before importing tools.mcp_server
class MockFastMCP:
    def __init__(self, *args, **kwargs):
        pass

    def tool(self, *args, **kwargs):
        """Decorator that returns the original function unchanged"""

        def decorator(func):
            return func

        if args and callable(args[0]):
            return args[0]
        return decorator

    def resource(self, *args, **kwargs):
        """Decorator that returns the original function unchanged"""

        def decorator(func):
            return func

        return decorator

    def run(self):
        """Mock run method"""
        pass


mock_module = MagicMock()
mock_module.FastMCP = MockFastMCP
mock_module.Context = MagicMock

sys.modules["fastmcp"] = mock_module
sys.modules["fastmcp.server"] = MagicMock()
sys.modules["fastmcp.server.dependencies"] = MagicMock()
sys.modules["fastmcp.server.dependencies"].get_context = MagicMock()

# Add repo root to sys.path so we can import tools.mcp_server
sys.path.insert(0, str(Path(__file__).parent.parent))


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
    "auto_apply": True,
}

SAMPLE_PATTERNS_FILE = {
    "patterns": [SAMPLE_PATTERN],
    "version": "1.0",
    "last_updated": "2025-10-19T10:00:00Z",
    "total_builds": 1,
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
            "frequency": 1,
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
            {"pattern_id": f"pattern-{i}", "frequency": 1} for i in range(3)
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
            p
            for p in patterns["patterns"]
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


class TestBootstrapPatterns:
    """Test bootstrap functionality for automatic pattern migration on startup."""

    def test_bootstrap_merges_project_patterns(self, tmp_path):
        """Test that bootstrap correctly merges project patterns into global storage."""
        from tools.mcp_server import bootstrap_patterns_on_startup

        # Setup: Create fake project patterns directory
        project_dir = tmp_path / "project"
        project_patterns = project_dir / ".context-foundry" / "patterns"
        project_patterns.mkdir(parents=True)

        project_data = {
            "patterns": [
                {
                    "pattern_id": "test-pattern-1",
                    "frequency": 1,
                    "issue": "Test 1",
                    "project_types": ["test"],
                },
                {
                    "pattern_id": "test-pattern-2",
                    "frequency": 1,
                    "issue": "Test 2",
                    "project_types": ["test"],
                },
            ],
            "version": "1.0",
            "last_updated": "2025-11-09",
            "total_builds": 1,
        }
        (project_patterns / "common-issues.json").write_text(json.dumps(project_data))

        # Setup: Create empty global patterns directory
        global_patterns = tmp_path / "global" / ".context-foundry" / "patterns"
        global_patterns.mkdir(parents=True)

        # Execute bootstrap
        with (
            patch("pathlib.Path.cwd", return_value=project_dir),
            patch("pathlib.Path.home", return_value=tmp_path / "global"),
        ):
            bootstrap_patterns_on_startup()

        # Assert: Global patterns now contain project patterns
        global_file = global_patterns / "common-issues.json"
        assert global_file.exists()

        global_data = json.loads(global_file.read_text())
        pattern_ids = [p["pattern_id"] for p in global_data["patterns"]]
        assert "test-pattern-1" in pattern_ids
        assert "test-pattern-2" in pattern_ids

        # Assert: Bootstrap marker created
        assert (global_patterns / ".bootstrap-done").exists()

    def test_bootstrap_only_runs_once(self, tmp_path):
        """Test that bootstrap doesn't run if marker exists."""
        from tools.mcp_server import bootstrap_patterns_on_startup

        # Setup: Create bootstrap marker
        project_dir = tmp_path / "project"
        global_patterns = tmp_path / "global" / ".context-foundry" / "patterns"
        global_patterns.mkdir(parents=True)
        (global_patterns / ".bootstrap-done").write_text("Already done")

        # Execute: Bootstrap should return early
        with (
            patch("pathlib.Path.cwd", return_value=project_dir),
            patch("pathlib.Path.home", return_value=tmp_path / "global"),
        ):
            bootstrap_patterns_on_startup()

        # Assert: No error raised (would fail if it tried to merge non-existent project dir)
        assert (global_patterns / ".bootstrap-done").exists()

    def test_bootstrap_skips_if_not_cf_project(self, tmp_path):
        """Test that bootstrap skips if not in a Context Foundry project."""
        from tools.mcp_server import bootstrap_patterns_on_startup

        # Setup: Empty directory (not a CF project)
        project_dir = tmp_path / "not-a-cf-project"
        project_dir.mkdir()

        global_dir = tmp_path / "global"

        # Execute
        with (
            patch("pathlib.Path.cwd", return_value=project_dir),
            patch("pathlib.Path.home", return_value=global_dir),
        ):
            bootstrap_patterns_on_startup()

        # Assert: No global patterns directory created
        assert not (global_dir / ".context-foundry").exists()

    def test_bootstrap_handles_multiple_pattern_types(self, tmp_path):
        """Test that bootstrap merges all pattern file types."""
        from tools.mcp_server import bootstrap_patterns_on_startup

        # Setup: Create multiple pattern files
        project_dir = tmp_path / "project"
        project_patterns = project_dir / ".context-foundry" / "patterns"
        project_patterns.mkdir(parents=True)

        # Common issues
        common_issues = {
            "patterns": [
                {"pattern_id": "issue-1", "frequency": 1, "project_types": ["test"]}
            ],
            "version": "1.0",
            "last_updated": "2025-11-09",
            "total_builds": 1,
        }
        (project_patterns / "common-issues.json").write_text(json.dumps(common_issues))

        # Scout learnings
        scout_learnings = {
            "learnings": [
                {
                    "learning_id": "learning-1",
                    "key_points": ["test"],
                    "project_types": ["test"],
                }
            ],
            "version": "1.0",
            "last_updated": "2025-11-09",
        }
        (project_patterns / "scout-learnings.json").write_text(
            json.dumps(scout_learnings)
        )

        # Setup global directory
        global_patterns = tmp_path / "global" / ".context-foundry" / "patterns"
        global_patterns.mkdir(parents=True)

        # Execute
        with (
            patch("pathlib.Path.cwd", return_value=project_dir),
            patch("pathlib.Path.home", return_value=tmp_path / "global"),
        ):
            bootstrap_patterns_on_startup()

        # Assert: Both pattern files merged
        assert (global_patterns / "common-issues.json").exists()
        assert (global_patterns / "scout-learnings.json").exists()

        # Verify contents
        issues_data = json.loads((global_patterns / "common-issues.json").read_text())
        assert len(issues_data["patterns"]) == 1
        assert issues_data["patterns"][0]["pattern_id"] == "issue-1"

        learnings_data = json.loads(
            (global_patterns / "scout-learnings.json").read_text()
        )
        assert len(learnings_data["learnings"]) == 1
        assert learnings_data["learnings"][0]["learning_id"] == "learning-1"

    def test_bootstrap_marker_contains_metadata(self, tmp_path):
        """Test that bootstrap marker contains useful metadata."""
        from tools.mcp_server import bootstrap_patterns_on_startup

        # Setup
        project_dir = tmp_path / "project"
        project_patterns = project_dir / ".context-foundry" / "patterns"
        project_patterns.mkdir(parents=True)

        project_data = {
            "patterns": [
                {"pattern_id": "p1", "frequency": 1, "project_types": ["test"]},
                {"pattern_id": "p2", "frequency": 1, "project_types": ["test"]},
            ],
            "version": "1.0",
            "last_updated": "2025-11-09",
            "total_builds": 1,
        }
        (project_patterns / "common-issues.json").write_text(json.dumps(project_data))

        global_patterns = tmp_path / "global" / ".context-foundry" / "patterns"
        global_patterns.mkdir(parents=True)

        # Execute
        with (
            patch("pathlib.Path.cwd", return_value=project_dir),
            patch("pathlib.Path.home", return_value=tmp_path / "global"),
        ):
            bootstrap_patterns_on_startup()

        # Assert: Marker contains metadata
        marker_file = global_patterns / ".bootstrap-done"
        assert marker_file.exists()

        marker_content = marker_file.read_text()
        assert "Bootstrapped on" in marker_content
        assert "Files merged: 1" in marker_content
        assert "New patterns added: 2" in marker_content

    def test_bootstrap_handles_invalid_json_gracefully(self, tmp_path):
        """Test that bootstrap continues even if a pattern file has invalid JSON."""
        from tools.mcp_server import bootstrap_patterns_on_startup

        # Setup
        project_dir = tmp_path / "project"
        project_patterns = project_dir / ".context-foundry" / "patterns"
        project_patterns.mkdir(parents=True)

        # Create invalid JSON file
        (project_patterns / "common-issues.json").write_text("{invalid json}")

        # Create valid file
        valid_data = {
            "learnings": [
                {"learning_id": "l1", "key_points": ["test"], "project_types": ["test"]}
            ],
            "version": "1.0",
            "last_updated": "2025-11-09",
        }
        (project_patterns / "scout-learnings.json").write_text(json.dumps(valid_data))

        global_patterns = tmp_path / "global" / ".context-foundry" / "patterns"
        global_patterns.mkdir(parents=True)

        # Execute: Should not crash
        with (
            patch("pathlib.Path.cwd", return_value=project_dir),
            patch("pathlib.Path.home", return_value=tmp_path / "global"),
        ):
            bootstrap_patterns_on_startup()

        # Assert: Valid file was still merged
        assert (global_patterns / "scout-learnings.json").exists()
        # Bootstrap marker should exist even with partial failure
        assert (global_patterns / ".bootstrap-done").exists()
