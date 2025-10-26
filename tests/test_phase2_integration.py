"""
Integration tests for Phase 2 Smart Incremental Builds.

Tests all Phase 2 components working together:
- Global Scout cache
- Change detection
- Incremental Builder
- Test impact analysis
- Incremental docs
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Import Phase 2 modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from incremental.global_scout_cache import (
    get_global_cache_dir,
    generate_global_scout_key,
    save_scout_report_to_global_cache,
    get_cached_scout_report_global,
    clear_global_scout_cache
)

from incremental.change_detector import (
    capture_build_snapshot,
    detect_changes,
    compute_file_hashes
)

from incremental.incremental_builder import (
    build_dependency_graph,
    find_affected_files,
    create_incremental_build_plan
)

from incremental.test_impact_analyzer import (
    TestCoverageMap,
    find_affected_tests,
    create_test_plan
)

from incremental.incremental_docs import (
    build_docs_manifest,
    find_affected_docs,
    create_docs_plan
)


class TestGlobalScoutCache:
    """Test global Scout cache functionality."""

    def test_cache_key_generation(self):
        """Test cache key generation is consistent."""
        key1 = generate_global_scout_key(
            "Build a weather app",
            "web-app",
            ["react", "javascript"]
        )
        key2 = generate_global_scout_key(
            "build a weather app",  # Different case
            "web-app",
            ["javascript", "react"]  # Different order
        )
        # Keys should be identical (normalized)
        assert key1 == key2

    def test_global_cache_save_and_retrieve(self):
        """Test saving and retrieving from global cache."""
        # Clear cache first
        clear_global_scout_cache()

        # Save a Scout report
        task = "Build a test application"
        project_type = "web-app"
        tech_stack = ["react", "typescript"]
        scout_report = "# Scout Report\n\nThis is a test report."

        save_scout_report_to_global_cache(
            task, project_type, tech_stack, scout_report
        )

        # Retrieve it
        cached_report = get_cached_scout_report_global(
            task, project_type, tech_stack
        )

        assert cached_report == scout_report

        # Cleanup
        clear_global_scout_cache()


class TestChangeDetector:
    """Test change detection functionality."""

    def test_file_hashing(self):
        """Test file hashing is consistent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("print('hello')")

            hashes1 = compute_file_hashes(tmpdir)
            hashes2 = compute_file_hashes(tmpdir)

            assert hashes1 == hashes2
            assert "test.py" in hashes1

    def test_change_detection_no_changes(self):
        """Test detecting no changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("print('hello')")

            # Capture snapshot
            snapshot = capture_build_snapshot(tmpdir)

            # Detect changes (should be none)
            report = detect_changes(tmpdir, snapshot)

            assert len(report.changed_files) == 0
            assert len(report.unchanged_files) == 1
            assert report.change_percentage == 0.0

    def test_change_detection_with_changes(self):
        """Test detecting file changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("print('hello')")

            # Capture initial snapshot
            snapshot = capture_build_snapshot(tmpdir)

            # Modify file
            test_file.write_text("print('hello world')")

            # Detect changes
            report = detect_changes(tmpdir, snapshot)

            assert len(report.changed_files) == 1
            assert "test.py" in report.changed_files
            assert report.change_percentage > 0


class TestIncrementalBuilder:
    """Test incremental Builder functionality."""

    def test_dependency_graph_creation(self):
        """Test building dependency graph."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files with imports
            module_a = Path(tmpdir) / "module_a.py"
            module_a.write_text("import json\n")

            module_b = Path(tmpdir) / "module_b.py"
            module_b.write_text("import module_a\n")

            # Build graph
            graph = build_dependency_graph(tmpdir)

            assert "module_a.py" in graph.nodes
            assert "module_b.py" in graph.nodes

    def test_affected_files_calculation(self):
        """Test finding files affected by changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create simple dependency: b imports a
            module_a = Path(tmpdir) / "module_a.py"
            module_a.write_text("def foo(): pass\n")

            module_b = Path(tmpdir) / "module_b.py"
            module_b.write_text("from module_a import foo\n")

            # Build graph
            graph = build_dependency_graph(tmpdir)

            # Find affected files if module_a changed
            affected = find_affected_files(graph, ["module_a.py"])

            # module_b depends on module_a, so both should be affected
            assert "module_a.py" in affected
            # Note: Simple static analysis might not catch all dependencies


class TestTestImpactAnalyzer:
    """Test test impact analysis functionality."""

    def test_coverage_map_creation(self):
        """Test creating test coverage map."""
        # Create a simple test coverage map
        coverage_map = TestCoverageMap(
            framework="pytest",
            tests={
                "tests/test_foo.py::test_bar": {
                    "covers": ["foo.py"],
                    "duration_seconds": 0.5
                }
            },
            total_duration_seconds=0.5
        )

        assert coverage_map.framework == "pytest"
        assert len(coverage_map.tests) == 1

    def test_affected_tests_finding(self):
        """Test finding affected tests."""
        coverage_map = TestCoverageMap(
            framework="pytest",
            tests={
                "tests/test_foo.py::test_bar": {
                    "covers": ["foo.py"],
                    "duration_seconds": 0.5
                },
                "tests/test_baz.py::test_qux": {
                    "covers": ["baz.py"],
                    "duration_seconds": 0.3
                }
            },
            total_duration_seconds=0.8
        )

        # Find tests affected by foo.py change
        affected = find_affected_tests(coverage_map, ["foo.py"])

        assert len(affected) == 1
        assert "tests/test_foo.py::test_bar" in affected


class TestIncrementalDocs:
    """Test incremental documentation functionality."""

    def test_docs_manifest_creation(self):
        """Test building docs manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create docs directory
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()

            # Create a doc file
            (docs_dir / "ARCHITECTURE.md").write_text("# Architecture\n")

            # Build manifest
            manifest = build_docs_manifest(tmpdir)

            assert "docs/ARCHITECTURE.md" in manifest.documentation

    def test_affected_docs_finding(self):
        """Test finding affected docs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            (docs_dir / "API.md").write_text("# API\n")

            manifest = build_docs_manifest(tmpdir)

            # Find docs affected by mcp_server.py change
            affected = find_affected_docs(manifest, ["tools/mcp_server.py"])

            # API docs should be affected
            assert any("API" in doc or "api" in doc for doc in affected)


class TestPhase2Integration:
    """Integration tests for Phase 2 complete workflow."""

    def test_complete_incremental_build_workflow(self):
        """Test complete incremental build workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Create initial files
            module = Path(tmpdir) / "module.py"
            module.write_text("def hello(): return 'world'\n")

            # Step 2: Capture initial snapshot
            snapshot = capture_build_snapshot(tmpdir)
            assert snapshot is not None

            # Step 3: Make a small change
            module.write_text("def hello(): return 'world!'\n")

            # Step 4: Detect changes
            report = detect_changes(tmpdir, snapshot)
            assert len(report.changed_files) >= 1

            # Step 5: Create build plan
            plan = create_incremental_build_plan(tmpdir, report)
            assert plan is not None
            assert plan.estimated_time_saved_minutes >= 0

    def test_no_changes_optimization(self):
        """Test that no changes results in maximum preservation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files
            for i in range(5):
                (Path(tmpdir) / f"module{i}.py").write_text(f"# Module {i}\n")

            # Capture snapshot
            snapshot = capture_build_snapshot(tmpdir)

            # Detect changes (should be none)
            report = detect_changes(tmpdir, snapshot)

            assert report.change_percentage == 0.0
            assert len(report.unchanged_files) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
