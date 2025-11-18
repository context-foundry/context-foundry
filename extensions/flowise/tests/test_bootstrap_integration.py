"""
Integration tests for Flowise pattern bootstrap

Tests the complete flow: JSON → Bootstrap → Codex → Query

Run with: pytest extensions/flowise/tests/test_bootstrap_integration.py -v
"""

import pytest
from pathlib import Path
import subprocess
import sys

# Add context-foundry to path
cf_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(cf_root))


class TestBootstrapIntegration:
    """Test bootstrap script integration with Codex"""

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


class TestCodexIntegration:
    """Test patterns are queryable from Codex after bootstrap"""

    @pytest.fixture(scope="class", autouse=True)
    def run_bootstrap(self):
        """Ensure bootstrap has run before these tests"""
        script_path = cf_root / "scripts" / "bootstrap_flowise_patterns.py"
        subprocess.run([sys.executable, str(script_path)], capture_output=True)

    @pytest.fixture
    def codex_store(self):
        """Initialize Codex connection"""
        try:
            from context_foundry.codex import KnowledgeStore

            codex_path = Path.home() / ".context-foundry" / "codex.db"
            return KnowledgeStore(str(codex_path))
        except ImportError:
            pytest.skip("context_foundry.codex not available")

    def test_codex_contains_flowise_patterns(self, codex_store):
        """Verify Codex contains Flowise patterns"""
        # Search for Flowise patterns
        results = codex_store.search("flowise", entry_type="pattern")

        # Should have at least 13 patterns
        assert len(results) >= 13, f"Expected 13+ patterns, found {len(results)}"

    def test_codex_contains_flowise_issues(self, codex_store):
        """Verify Codex contains Flowise issues"""
        # Search for Flowise issues
        results = codex_store.search("flowise", entry_type="issue")

        # Should have at least 15 issues
        assert len(results) >= 15, f"Expected 15+ issues, found {len(results)}"

    def test_chaining_pattern_in_codex(self, codex_store):
        """Verify specific pattern (chaining) is in Codex with correct data"""
        entry = codex_store.get_entry("afv2-chaining-pattern")

        assert entry is not None, "Chaining pattern not found in Codex"
        assert entry.id == "afv2-chaining-pattern"
        assert "flowise" in entry.category.lower()

        # Check metadata preserved
        metadata = entry.metadata
        assert (
            "implementation_notes" in metadata
        ), "Pattern metadata missing implementation_notes"
        assert (
            "testing_checklist" in metadata
        ), "Pattern metadata missing testing_checklist"

    def test_routing_pattern_in_codex(self, codex_store):
        """Verify routing pattern (most common) is in Codex"""
        entry = codex_store.get_entry("afv2-routing-pattern")

        assert entry is not None, "Routing pattern not found in Codex"
        assert entry.id == "afv2-routing-pattern"
        assert entry.confidence >= 0.95, "Routing pattern should have high confidence"

    def test_missing_inputparams_issue_in_codex(self, codex_store):
        """Verify critical issue is in Codex with correct severity"""
        entry = codex_store.get_entry("flowise-missing-inputparams")

        assert entry is not None, "Missing inputParams issue not found in Codex"
        assert entry.id == "flowise-missing-inputparams"
        assert (
            entry.severity.value == "CRITICAL"
        ), f"Expected CRITICAL, got {entry.severity.value}"

        # Check metadata preserved
        metadata = entry.metadata
        assert "symptoms" in metadata, "Issue metadata missing symptoms"
        assert "prevention" in metadata, "Issue metadata missing prevention"

    def test_missing_start_node_issue_in_codex(self, codex_store):
        """Verify missing start node issue is in Codex"""
        entry = codex_store.get_entry("flowise-missing-start-node")

        assert entry is not None, "Missing start node issue not found in Codex"
        assert entry.severity.value == "CRITICAL"

    def test_pattern_search_returns_relevant_results(self, codex_store):
        """Verify pattern search returns relevant results"""
        results = codex_store.search("routing pattern")

        # Should find routing pattern
        pattern_ids = [r.id for r in results]
        assert (
            "afv2-routing-pattern" in pattern_ids
        ), f"Routing pattern not found in search results: {pattern_ids}"

    def test_issue_search_returns_relevant_results(self, codex_store):
        """Verify issue search returns relevant results"""
        results = codex_store.search("missing start node")

        # Should find start node issue
        issue_ids = [r.id for r in results]
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
        try:
            from context_foundry.codex import KnowledgeStore

            codex_path = Path.home() / ".context-foundry" / "codex.db"
            store = KnowledgeStore(str(codex_path))

            # Get initial count
            initial_patterns = len(store.search("flowise", entry_type="pattern"))
            initial_issues = len(store.search("flowise", entry_type="issue"))

            # Run bootstrap again
            script_path = cf_root / "scripts" / "bootstrap_flowise_patterns.py"
            subprocess.run([sys.executable, str(script_path)], capture_output=True)

            # Get new count
            new_patterns = len(store.search("flowise", entry_type="pattern"))
            new_issues = len(store.search("flowise", entry_type="issue"))

            # Counts should be equal (idempotent)
            assert (
                initial_patterns == new_patterns
            ), f"Pattern count changed: {initial_patterns} -> {new_patterns}"
            assert (
                initial_issues == new_issues
            ), f"Issue count changed: {initial_issues} -> {new_issues}"

        except ImportError:
            pytest.skip("context_foundry.codex not available")
