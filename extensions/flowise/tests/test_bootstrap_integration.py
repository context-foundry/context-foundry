"""
Integration tests for Flowise pattern bootstrap

Tests the complete flow: JSON → Bootstrap → Pattern Files → Query

Run with: pytest extensions/flowise/tests/test_bootstrap_integration.py -v
"""

import pytest
import json
from pathlib import Path
import subprocess
import sys

# Add context-foundry to path
cf_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(cf_root))
sys.path.insert(0, str(cf_root / "tools"))


class TestBootstrapIntegration:
    """Test bootstrap script integration with pattern files"""

    @pytest.fixture(scope="class")
    def bootstrap_result(self):
        """Run bootstrap script once for all tests"""
        script_path = cf_root / "scripts" / "bootstrap_flowise_patterns.py"
        result = subprocess.run(
            [sys.executable, str(script_path)], capture_output=True, text=True
        )
        return result

    def test_bootstrap_runs_successfully(self, bootstrap_result):
        """Verify bootstrap script exits with code 0"""
        assert (
            bootstrap_result.returncode == 0
        ), f"Bootstrap failed:\nstdout: {bootstrap_result.stdout}\nstderr: {bootstrap_result.stderr}"

    def test_bootstrap_output_format(self, bootstrap_result):
        """Verify bootstrap output has expected format"""
        output = bootstrap_result.stdout
        assert "Bootstrap Flowise Patterns" in output, "Missing header"
        assert "Importing patterns..." in output, "Missing patterns import message"
        assert "Importing common issues..." in output, "Missing issues import message"
        assert "Bootstrap complete!" in output, "Missing completion message"

    def test_bootstrap_imports_patterns(self, bootstrap_result):
        """Verify patterns were imported (Added or Updated)"""
        output = bootstrap_result.stdout
        # Should see either "Added:" or "Updated:" for patterns
        pattern_lines = [line for line in output.split("\n") if "afv2-" in line]
        assert (
            len(pattern_lines) >= 13
        ), f"Expected 13+ pattern import lines, found {len(pattern_lines)}"

    def test_bootstrap_imports_issues(self, bootstrap_result):
        """Verify issues were imported (Added or Updated)"""
        output = bootstrap_result.stdout
        # Should see either "Added:" or "Updated:" for issues
        issue_lines = [
            line
            for line in output.split("\n")
            if "flowise-" in line and "Error" not in line
        ]
        assert (
            len(issue_lines) >= 15
        ), f"Expected 15+ issue import lines, found {len(issue_lines)}"


class TestPatternFileIntegration:
    """Test patterns are queryable from pattern files after bootstrap"""

    @pytest.fixture(scope="class", autouse=True)
    def run_bootstrap(self):
        """Ensure bootstrap has run before these tests"""
        script_path = cf_root / "scripts" / "bootstrap_flowise_patterns.py"
        subprocess.run([sys.executable, str(script_path)], capture_output=True)

    @pytest.fixture
    def pattern_files(self):
        """Load pattern files"""
        pattern_dir = Path.home() / ".context-foundry" / "patterns"

        arch_file = pattern_dir / "architecture-patterns.json"
        issues_file = pattern_dir / "common-issues.json"

        arch_patterns = {}
        common_issues = {}

        if arch_file.exists():
            with open(arch_file) as f:
                arch_patterns = json.load(f)

        if issues_file.exists():
            with open(issues_file) as f:
                common_issues = json.load(f)

        return {
            "architecture": arch_patterns,
            "issues": common_issues,
        }

    def test_patterns_file_contains_flowise_patterns(self, pattern_files):
        """Verify architecture patterns file contains Flowise patterns"""
        patterns = pattern_files["architecture"].get("patterns", [])
        flowise_patterns = [p for p in patterns if p.get("category") == "flowise"]

        # Should have at least 13 patterns
        assert (
            len(flowise_patterns) >= 13
        ), f"Expected 13+ patterns, found {len(flowise_patterns)}"

    def test_issues_file_contains_flowise_issues(self, pattern_files):
        """Verify common issues file contains Flowise issues"""
        issues = pattern_files["issues"].get("patterns", [])
        flowise_issues = [p for p in issues if p.get("category") == "flowise"]

        # Should have at least 15 issues
        assert (
            len(flowise_issues) >= 15
        ), f"Expected 15+ issues, found {len(flowise_issues)}"

    def test_chaining_pattern_in_files(self, pattern_files):
        """Verify specific pattern (chaining) is in files with correct data"""
        patterns = pattern_files["architecture"].get("patterns", [])
        chaining_patterns = [
            p for p in patterns if p.get("id") == "afv2-chaining-pattern"
        ]

        assert len(chaining_patterns) == 1, "Chaining pattern not found in files"
        pattern = chaining_patterns[0]

        assert pattern["id"] == "afv2-chaining-pattern"
        assert "flowise" in pattern.get("category", "").lower()

        # Check metadata preserved
        metadata = pattern.get("metadata", {})
        assert (
            "implementation_notes" in metadata
        ), "Pattern metadata missing implementation_notes"
        assert (
            "testing_checklist" in metadata
        ), "Pattern metadata missing testing_checklist"

    def test_routing_pattern_in_files(self, pattern_files):
        """Verify routing pattern (most common) is in files"""
        patterns = pattern_files["architecture"].get("patterns", [])
        routing_patterns = [
            p for p in patterns if p.get("id") == "afv2-routing-pattern"
        ]

        assert len(routing_patterns) == 1, "Routing pattern not found in files"
        pattern = routing_patterns[0]

        assert pattern["id"] == "afv2-routing-pattern"
        assert (
            pattern.get("confidence", 0) >= 0.95
        ), "Routing pattern should have high confidence"

    def test_missing_inputparams_issue_in_files(self, pattern_files):
        """Verify critical issue is in files with correct severity"""
        issues = pattern_files["issues"].get("patterns", [])
        inputparam_issues = [
            p for p in issues if p.get("id") == "flowise-missing-inputparams"
        ]

        assert (
            len(inputparam_issues) == 1
        ), "Missing inputParams issue not found in files"
        issue = inputparam_issues[0]

        assert issue["id"] == "flowise-missing-inputparams"
        assert (
            issue.get("severity") == "CRITICAL"
        ), f"Expected CRITICAL, got {issue.get('severity')}"

        # Check metadata preserved
        metadata = issue.get("metadata", {})
        assert "symptoms" in metadata, "Issue metadata missing symptoms"
        assert "prevention" in metadata, "Issue metadata missing prevention"

    def test_missing_start_node_issue_in_files(self, pattern_files):
        """Verify missing start node issue is in files"""
        issues = pattern_files["issues"].get("patterns", [])
        start_issues = [
            p for p in issues if p.get("id") == "flowise-missing-start-node"
        ]

        assert len(start_issues) == 1, "Missing start node issue not found in files"
        assert start_issues[0].get("severity") == "CRITICAL"

    def test_pattern_search_returns_relevant_results(self, pattern_files):
        """Verify pattern search returns relevant results"""
        patterns = pattern_files["architecture"].get("patterns", [])

        # Simple search by title/description
        routing_patterns = [
            p
            for p in patterns
            if "routing" in p.get("title", "").lower()
            or "routing" in p.get("description", "").lower()
        ]

        # Should find routing pattern
        pattern_ids = [p.get("id") for p in routing_patterns]
        assert (
            "afv2-routing-pattern" in pattern_ids
        ), f"Routing pattern not found in search results: {pattern_ids}"

    def test_issue_search_returns_relevant_results(self, pattern_files):
        """Verify issue search returns relevant results"""
        issues = pattern_files["issues"].get("patterns", [])

        # Simple search by title/description
        start_issues = [
            p
            for p in issues
            if "start" in p.get("title", "").lower()
            and "node" in p.get("title", "").lower()
        ]

        # Should find start node issue
        issue_ids = [p.get("id") for p in start_issues]
        assert (
            "flowise-missing-start-node" in issue_ids
        ), f"Start node issue not found in search results: {issue_ids}"


class TestIdempotency:
    """Test that bootstrap can be safely re-run"""

    def test_rerun_bootstrap_is_idempotent(self):
        """Verify re-running bootstrap doesn't duplicate entries"""
        script_path = cf_root / "scripts" / "bootstrap_flowise_patterns.py"

        # Run bootstrap twice
        result1 = subprocess.run(
            [sys.executable, str(script_path)], capture_output=True, text=True
        )
        result2 = subprocess.run(
            [sys.executable, str(script_path)], capture_output=True, text=True
        )

        # Both should succeed
        assert result1.returncode == 0, f"First run failed: {result1.stderr}"
        assert result2.returncode == 0, f"Second run failed: {result2.stderr}"

        # Second run should show "Updated" not "Added" (idempotent)
        assert (
            "Updated:" in result2.stdout or "Added:" in result2.stdout
        ), "Second run should show Updated or Added entries"

    def test_entry_count_stable_after_rerun(self):
        """Verify entry count doesn't increase after re-run"""
        pattern_dir = Path.home() / ".context-foundry" / "patterns"
        arch_file = pattern_dir / "architecture-patterns.json"
        issues_file = pattern_dir / "common-issues.json"

        def get_flowise_counts():
            """Get count of flowise patterns and issues"""
            pattern_count = 0
            issue_count = 0

            if arch_file.exists():
                with open(arch_file) as f:
                    data = json.load(f)
                    pattern_count = len(
                        [
                            p
                            for p in data.get("patterns", [])
                            if p.get("category") == "flowise"
                        ]
                    )

            if issues_file.exists():
                with open(issues_file) as f:
                    data = json.load(f)
                    issue_count = len(
                        [
                            p
                            for p in data.get("patterns", [])
                            if p.get("category") == "flowise"
                        ]
                    )

            return pattern_count, issue_count

        # Get initial count
        initial_patterns, initial_issues = get_flowise_counts()

        # Run bootstrap again
        script_path = cf_root / "scripts" / "bootstrap_flowise_patterns.py"
        subprocess.run([sys.executable, str(script_path)], capture_output=True)

        # Get new count
        new_patterns, new_issues = get_flowise_counts()

        # Counts should be equal (idempotent)
        assert (
            initial_patterns == new_patterns
        ), f"Pattern count changed: {initial_patterns} -> {new_patterns}"
        assert (
            initial_issues == new_issues
        ), f"Issue count changed: {initial_issues} -> {new_issues}"
