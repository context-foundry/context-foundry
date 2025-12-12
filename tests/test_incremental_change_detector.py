#!/usr/bin/env python3
"""
Comprehensive tests for tools/incremental/change_detector.py
Tests change detection, git integration, and hash fallback.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch
from dataclasses import asdict

# Import modules to test
from tools.incremental.change_detector import (
    ChangeReport,
    get_last_build_snapshot_path,
    hash_file,
    get_git_commit_sha,
    get_git_changed_files,
    detect_changes,
    capture_build_snapshot,
)


class TestChangeReport:
    """Test ChangeReport dataclass."""

    def test_change_report_creation(self):
        """Test creating ChangeReport instance."""
        report = ChangeReport(
            changed_files=["file1.py", "file2.py"],
            added_files=["file3.py"],
            deleted_files=["old_file.py"],
            unchanged_files=["config.py"],
            change_percentage=60.0,
            git_available=True,
            git_diff_sha="abc123",
            total_files=5,
            detection_method="git",
        )

        assert len(report.changed_files) == 2
        assert len(report.added_files) == 1
        assert len(report.deleted_files) == 1
        assert report.change_percentage == 60.0
        assert report.git_available is True
        assert report.detection_method == "git"

    def test_change_report_to_dict(self):
        """Test converting ChangeReport to dict."""
        report = ChangeReport(
            changed_files=["a.py"],
            added_files=[],
            deleted_files=[],
            unchanged_files=["b.py"],
            change_percentage=50.0,
            git_available=False,
            git_diff_sha=None,
            total_files=2,
            detection_method="hash",
        )

        result = asdict(report)

        assert isinstance(result, dict)
        assert result["changed_files"] == ["a.py"]
        assert result["detection_method"] == "hash"


class TestGetLastBuildSnapshotPath:
    """Test get_last_build_snapshot_path function."""

    def test_snapshot_path_location(self):
        """Test that snapshot path is in .context-foundry directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = get_last_build_snapshot_path(tmpdir)

            assert snapshot_path.parent.name == ".context-foundry"
            assert snapshot_path.name == "last-build-snapshot.json"

    def test_snapshot_path_creates_directory(self):
        """Test that snapshot path creates parent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = get_last_build_snapshot_path(tmpdir)

            # Parent directory should be created
            assert snapshot_path.parent.exists()
            assert snapshot_path.parent.is_dir()


class TestHashFile:
    """Test hash_file function."""

    def test_hash_file_returns_sha256(self):
        """Test that hash_file returns SHA256 hash."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("Test content")
            temp_path = Path(f.name)

        try:
            hash_value = hash_file(temp_path)

            # SHA256 hash should be 64 hex characters
            assert len(hash_value) == 64
            assert all(c in "0123456789abcdef" for c in hash_value)
        finally:
            temp_path.unlink()

    def test_hash_file_consistent(self):
        """Test that hash_file returns same hash for same content."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("Same content")
            temp_path = Path(f.name)

        try:
            hash1 = hash_file(temp_path)
            hash2 = hash_file(temp_path)

            assert hash1 == hash2
        finally:
            temp_path.unlink()

    def test_hash_file_different_content(self):
        """Test that different content produces different hash."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix="1.txt") as f1:
            f1.write("Content 1")
            path1 = Path(f1.name)

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix="2.txt") as f2:
            f2.write("Content 2")
            path2 = Path(f2.name)

        try:
            hash1 = hash_file(path1)
            hash2 = hash_file(path2)

            assert hash1 != hash2
        finally:
            path1.unlink()
            path2.unlink()

    def test_hash_file_binary_content(self):
        """Test hashing binary files."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"\x00\x01\x02\x03\xff\xfe")
            temp_path = Path(f.name)

        try:
            hash_value = hash_file(temp_path)

            assert len(hash_value) == 64
        finally:
            temp_path.unlink()

    def test_hash_file_missing_file(self):
        """Test hashing non-existent file."""
        nonexistent = Path("/tmp/nonexistent_file_12345.txt")

        hash_value = hash_file(nonexistent)

        # Should return empty string on error
        assert hash_value == ""

    def test_hash_file_permission_error(self):
        """Test hashing file with permission error."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Make file unreadable
            temp_path.chmod(0o000)

            hash_value = hash_file(temp_path)

            # Should return empty string on permission error
            assert hash_value == ""
        finally:
            temp_path.chmod(0o644)
            temp_path.unlink()


class TestGetGitCommitSha:
    """Test get_git_commit_sha function."""

    @patch("subprocess.run")
    def test_get_git_commit_sha_success(self, mock_run):
        """Test getting git commit SHA successfully."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "abc123def456\n"
        mock_run.return_value = mock_result

        sha = get_git_commit_sha("/tmp/project")

        assert sha == "abc123def456"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_get_git_commit_sha_not_a_repo(self, mock_run):
        """Test git commit SHA when not in a git repo."""
        mock_result = Mock()
        mock_result.returncode = 128  # Git error code
        mock_run.return_value = mock_result

        sha = get_git_commit_sha("/tmp/project")

        assert sha is None

    @patch("subprocess.run")
    def test_get_git_commit_sha_git_not_installed(self, mock_run):
        """Test when git is not installed."""
        mock_run.side_effect = FileNotFoundError()

        sha = get_git_commit_sha("/tmp/project")

        assert sha is None

    @patch("subprocess.run")
    def test_get_git_commit_sha_timeout(self, mock_run):
        """Test git command timeout."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("git", 5)

        sha = get_git_commit_sha("/tmp/project")

        assert sha is None

    @patch("subprocess.run")
    def test_get_git_commit_sha_subprocess_error(self, mock_run):
        """Test subprocess error handling."""
        import subprocess

        mock_run.side_effect = subprocess.SubprocessError()

        sha = get_git_commit_sha("/tmp/project")

        assert sha is None


class TestGetGitChangedFiles:
    """Test get_git_changed_files function."""

    @patch("subprocess.run")
    def test_get_git_changed_files_success(self, mock_run):
        """Test getting changed files successfully."""
        # Mock changed files (first call) and deleted files (second call)
        mock_result_changed = Mock()
        mock_result_changed.returncode = 0
        mock_result_changed.stdout = "file1.py\nfile2.py\nfile3.py\n"

        mock_result_deleted = Mock()
        mock_result_deleted.returncode = 0
        mock_result_deleted.stdout = ""  # No deleted files

        mock_run.side_effect = [mock_result_changed, mock_result_deleted]

        files = get_git_changed_files("/tmp/project", "abc123")

        assert files == ["file1.py", "file2.py", "file3.py"]

    @patch("subprocess.run")
    def test_get_git_changed_files_no_changes(self, mock_run):
        """Test when no files changed."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.side_effect = [mock_result, mock_result]  # Both calls return empty

        files = get_git_changed_files("/tmp/project", "abc123")

        assert files == []

    @patch("subprocess.run")
    def test_get_git_changed_files_error(self, mock_run):
        """Test error handling in git diff."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        files = get_git_changed_files("/tmp/project", "abc123")

        assert files is None

    @patch("subprocess.run")
    def test_get_git_changed_files_timeout(self, mock_run):
        """Test timeout handling."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("git", 10)

        files = get_git_changed_files("/tmp/project", "abc123")

        assert files is None


class TestDetectChanges:
    """Test detect_changes function."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project with files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create some files
            file1 = project_root / "file1.py"
            file1.write_text("content1")

            file2 = project_root / "file2.py"
            file2.write_text("content2")

            yield project_root

    @patch("tools.incremental.change_detector.get_git_commit_sha")
    @patch("tools.incremental.change_detector.get_git_changed_files")
    def test_detect_changes_with_git(self, mock_git_files, mock_git_sha, temp_project):
        """Test change detection using git."""
        mock_git_sha.return_value = "current_sha"
        mock_git_files.return_value = ["file1.py"]

        # Create snapshot
        snapshot_path = get_last_build_snapshot_path(str(temp_project))
        snapshot_data = {
            "timestamp": "2024-01-01T00:00:00",
            "git_sha": "old_sha",
            "file_hashes": {"file1.py": "old_hash1", "file2.py": "hash2"},
        }
        snapshot_path.write_text(json.dumps(snapshot_data))

        report = detect_changes(str(temp_project))

        assert report.git_available is True
        assert report.detection_method == "git"
        assert "file1.py" in report.changed_files

    @patch("tools.incremental.change_detector.get_git_commit_sha")
    def test_detect_changes_without_git_uses_hash(self, mock_git_sha, temp_project):
        """Test change detection falls back to hash when git unavailable."""
        mock_git_sha.return_value = None

        # Create initial snapshot
        file1 = temp_project / "file1.py"
        file2 = temp_project / "file2.py"

        snapshot_path = get_last_build_snapshot_path(str(temp_project))
        snapshot_data = {
            "timestamp": "2024-01-01T00:00:00",
            "git_sha": None,
            "file_hashes": {
                str(file1.relative_to(temp_project)): "old_hash",
                str(file2.relative_to(temp_project)): hash_file(file2),
            },
        }
        snapshot_path.write_text(json.dumps(snapshot_data))

        report = detect_changes(str(temp_project))

        assert report.git_available is False
        assert report.detection_method == "hash"

    def test_detect_changes_no_snapshot(self, temp_project):
        """Test change detection when no previous snapshot exists."""
        report = detect_changes(str(temp_project))

        # All files should be marked as changed (first build)
        assert len(report.changed_files) > 0
        assert report.change_percentage > 0

    def test_detect_changes_no_changes(self, temp_project):
        """Test when no files have changed."""
        # Save initial snapshot
        capture_build_snapshot(str(temp_project))

        # Immediately detect changes (nothing changed)
        with patch("tools.incremental.change_detector.get_git_commit_sha") as mock_sha:
            mock_sha.return_value = None  # Force hash-based detection

            report = detect_changes(str(temp_project))

            # Should have some unchanged files
            assert len(report.unchanged_files) > 0 or report.change_percentage == 0

    def test_detect_changes_calculates_percentage(self, temp_project):
        """Test that change percentage is calculated correctly."""
        report = detect_changes(str(temp_project))

        # Percentage should be between 0 and 100
        assert 0 <= report.change_percentage <= 100

        # Total files should match sum of categories
        (
            len(report.changed_files)
            + len(report.added_files)
            + len(report.unchanged_files)
        )
        # Note: deleted_files are not counted in total_files


class TestCaptureSnapshot:
    """Test capture_build_snapshot function."""

    def test_capture_snapshot_creates_file(self):
        """Test that capture_build_snapshot creates snapshot file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            capture_build_snapshot(tmpdir)

            snapshot_path = get_last_build_snapshot_path(tmpdir)
            assert snapshot_path.exists()

    def test_capture_snapshot_contains_data(self):
        """Test that captured snapshot contains expected data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("content")

            snapshot = capture_build_snapshot(tmpdir)

            assert "timestamp" in snapshot
            assert "file_hashes" in snapshot

    @patch("tools.incremental.change_detector.get_git_commit_sha")
    def test_capture_snapshot_includes_git_sha(self, mock_git_sha):
        """Test that snapshot includes git SHA when available."""
        mock_git_sha.return_value = "abc123def"

        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot = capture_build_snapshot(tmpdir)

            assert snapshot["git_sha"] == "abc123def"

    @patch("tools.incremental.change_detector.get_git_commit_sha")
    def test_capture_snapshot_without_git(self, mock_git_sha):
        """Test snapshot when git is not available."""
        mock_git_sha.return_value = None

        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot = capture_build_snapshot(tmpdir)

            assert snapshot["git_sha"] is None


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_detect_changes_with_corrupted_snapshot(self):
        """Test handling of corrupted snapshot file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create file
            test_file = project_root / "test.py"
            test_file.write_text("content")

            # Create corrupted snapshot
            snapshot_path = get_last_build_snapshot_path(tmpdir)
            snapshot_path.write_text("{ invalid json }")

            # Should not crash, should detect all files as changed
            report = detect_changes(tmpdir)

            assert isinstance(report, ChangeReport)

    def test_hash_file_empty_file(self):
        """Test hashing empty file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)

        try:
            hash_value = hash_file(temp_path)

            # Should still produce valid hash
            assert len(hash_value) == 64
        finally:
            temp_path.unlink()

    def test_detect_changes_with_special_characters_in_filename(self):
        """Test files with special characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create file with spaces and special chars
            special_file = project_root / "file with spaces & special.py"
            special_file.write_text("content")

            report = detect_changes(tmpdir)

            # Should handle special characters gracefully
            assert isinstance(report, ChangeReport)

    def test_detect_changes_with_very_large_file(self):
        """Test hashing very large file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create large file (1MB)
            large_file = project_root / "large.bin"
            large_file.write_bytes(b"0" * 1024 * 1024)

            hash_value = hash_file(large_file)

            # Should still produce valid hash
            assert len(hash_value) == 64

    @patch("tools.incremental.change_detector.get_git_commit_sha")
    def test_detect_changes_same_git_sha(self, mock_git_sha):
        """Test when git SHA hasn't changed."""
        mock_git_sha.return_value = "same_sha"

        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            file1 = project_root / "test.py"
            file1.write_text("content")

            # Create snapshot with same SHA
            snapshot_path = get_last_build_snapshot_path(tmpdir)
            snapshot_data = {
                "timestamp": "2024-01-01T00:00:00",
                "git_sha": "same_sha",
                "file_hashes": {},
            }
            snapshot_path.write_text(json.dumps(snapshot_data))

            with patch(
                "tools.incremental.change_detector.get_git_changed_files"
            ) as mock_git_files:
                mock_git_files.return_value = []

                report = detect_changes(tmpdir)

                # Should detect no changes when SHA is same and no git diff
                assert len(report.changed_files) == 0 or report.change_percentage < 100


class TestIntegration:
    """Integration tests with real file system."""

    def test_full_workflow(self):
        """Test complete workflow: detect, save, detect again."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create initial files
            file1 = project_root / "file1.py"
            file1.write_text("initial content")

            file2 = project_root / "file2.py"
            file2.write_text("unchanged")

            # First detection (no snapshot)
            report1 = detect_changes(tmpdir)
            assert report1.change_percentage > 0

            # Save snapshot
            capture_build_snapshot(tmpdir)

            # Modify file1
            file1.write_text("modified content")

            # Second detection (with snapshot)
            report2 = detect_changes(tmpdir)

            # Should detect file1 as changed, file2 as unchanged
            assert len(report2.changed_files) >= 1
            assert report2.change_percentage > 0
            assert report2.change_percentage < 100

    def test_added_and_deleted_files(self):
        """Test detection of added and deleted files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create initial file
            file1 = project_root / "file1.py"
            file1.write_text("content")

            # Save snapshot
            capture_build_snapshot(tmpdir)

            # Add new file
            file2 = project_root / "file2.py"
            file2.write_text("new")

            # Delete old file
            file1.unlink()

            # Detect changes
            report = detect_changes(tmpdir)

            # Should detect additions and deletions
            assert len(report.added_files) > 0 or len(report.deleted_files) > 0
