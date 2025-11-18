"""
Unit tests for Flowise patterns loading

Run with: pytest extensions/flowise/tests/test_patterns.py -v
"""

import pytest
from pathlib import Path
import json
import sys

# Add context-foundry to path
cf_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(cf_root))


class TestFlowisePatterns:
    """Test pattern loading and structure"""

    @pytest.fixture
    def patterns_data(self):
        """Load flowise-expertise.json"""
        patterns_file = (
            cf_root / "extensions" / "flowise" / "patterns" / "flowise-expertise.json"
        )
        with open(patterns_file, "r") as f:
            return json.load(f)

    def test_loads_patterns(self, patterns_data):
        """Verify pattern JSON loads without errors"""
        assert patterns_data is not None
        assert "patterns" in patterns_data
        assert "common_issues" in patterns_data
        assert len(patterns_data["patterns"]) > 0

    def test_pattern_count(self, patterns_data):
        """Verify expected number of patterns"""
        assert (
            len(patterns_data["patterns"]) == 13
        ), f"Should have 13 AFv2 workflow patterns, found {len(patterns_data['patterns'])}"
        assert (
            len(patterns_data["common_issues"]) == 15
        ), f"Should have 15 common issues, found {len(patterns_data['common_issues'])}"

    def test_pattern_structure(self, patterns_data):
        """Verify each pattern has required fields"""
        required_fields = [
            "pattern_id",
            "category",
            "applies_to",
            "description",
            "confidence",
        ]

        for pattern in patterns_data["patterns"]:
            for field in required_fields:
                assert (
                    field in pattern
                ), f"Pattern {pattern.get('pattern_id', 'unknown')} missing required field: {field}"

            # Validate types
            assert isinstance(pattern["pattern_id"], str), "pattern_id must be string"
            assert isinstance(pattern["category"], str), "category must be string"
            assert isinstance(pattern["applies_to"], list), "applies_to must be list"
            assert isinstance(
                pattern["confidence"], (int, float)
            ), "confidence must be number"
            assert (
                0.0 <= pattern["confidence"] <= 1.0
            ), "confidence must be between 0 and 1"

    def test_chaining_pattern_details(self, patterns_data):
        """Verify chaining pattern has detailed structure"""
        chaining = None
        for pattern in patterns_data["patterns"]:
            if pattern["pattern_id"] == "afv2-chaining-pattern":
                chaining = pattern
                break

        assert chaining is not None, "Chaining pattern not found"
        assert (
            "implementation_notes" in chaining
        ), "Chaining pattern missing implementation_notes"
        assert "use_cases" in chaining, "Chaining pattern missing use_cases"
        assert (
            "testing_checklist" in chaining
        ), "Chaining pattern missing testing_checklist"
        assert (
            len(chaining["implementation_notes"]) > 0
        ), "implementation_notes should not be empty"

    def test_routing_pattern_exists(self, patterns_data):
        """Verify routing pattern (most common) exists"""
        routing = None
        for pattern in patterns_data["patterns"]:
            if pattern["pattern_id"] == "afv2-routing-pattern":
                routing = pattern
                break

        assert routing is not None, "Routing pattern not found"
        assert (
            routing["confidence"] >= 0.95
        ), "Routing pattern should have high confidence"
        assert (
            "flowise-agentflow" in routing["applies_to"]
        ), "Routing pattern should apply to flowise-agentflow"

    def test_common_issues_structure(self, patterns_data):
        """Verify common issues have required fields"""
        required_fields = [
            "issue_id",
            "severity",
            "description",
            "symptoms",
            "solution",
            "prevention",
        ]

        valid_severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

        for issue in patterns_data["common_issues"]:
            for field in required_fields:
                assert (
                    field in issue
                ), f"Issue {issue.get('issue_id', 'unknown')} missing required field: {field}"

            # Validate severity
            assert (
                issue["severity"] in valid_severities
            ), f"Invalid severity: {issue['severity']}"

    def test_missing_inputparams_issue(self, patterns_data):
        """Verify critical missing inputParams issue is documented"""
        issue = None
        for i in patterns_data["common_issues"]:
            if i["issue_id"] == "flowise-missing-inputparams":
                issue = i
                break

        assert issue is not None, "Missing inputParams issue not found"
        assert (
            issue["severity"] == "CRITICAL"
        ), "Missing inputParams should be CRITICAL severity"
        assert "symptoms" in issue, "Issue missing symptoms"
        assert "code_fix" in issue, "Issue missing code_fix"
        assert len(issue["prevention"]) > 0, "Issue should have prevention steps"

    def test_missing_start_node_issue(self, patterns_data):
        """Verify missing start node issue is documented"""
        issue = None
        for i in patterns_data["common_issues"]:
            if i["issue_id"] == "flowise-missing-start-node":
                issue = i
                break

        assert issue is not None, "Missing start node issue not found"
        assert (
            issue["severity"] == "CRITICAL"
        ), "Missing start node should be CRITICAL severity"
        assert (
            "formTitle" in issue["code_fix"] or "Start" in issue["code_fix"]
        ), "Code fix should show Start node example"

    def test_pattern_ids_unique(self, patterns_data):
        """Verify no duplicate pattern IDs"""
        pattern_ids = [p["pattern_id"] for p in patterns_data["patterns"]]
        assert (
            len(pattern_ids) == len(set(pattern_ids))
        ), f"Duplicate pattern IDs found: {[x for x in pattern_ids if pattern_ids.count(x) > 1]}"

        issue_ids = [i["issue_id"] for i in patterns_data["common_issues"]]
        assert (
            len(issue_ids) == len(set(issue_ids))
        ), f"Duplicate issue IDs found: {[x for x in issue_ids if issue_ids.count(x) > 1]}"

    def test_project_types_valid(self, patterns_data):
        """Verify project types are consistent"""
        for pattern in patterns_data["patterns"]:
            assert (
                "flowise-agentflow" in pattern["applies_to"]
            ), f"Pattern {pattern['pattern_id']} missing flowise-agentflow project type"

    def test_all_patterns_have_testing_checklist(self, patterns_data):
        """Verify all patterns have testing guidance"""
        for pattern in patterns_data["patterns"]:
            assert (
                "testing_checklist" in pattern
            ), f"Pattern {pattern['pattern_id']} missing testing_checklist"
            assert (
                len(pattern["testing_checklist"]) >= 3
            ), f"Pattern {pattern['pattern_id']} should have at least 3 testing checklist items"

    def test_version_info(self, patterns_data):
        """Verify pattern file has version metadata"""
        assert "version" in patterns_data, "Missing version field"
        assert "last_updated" in patterns_data, "Missing last_updated field"
        assert "description" in patterns_data, "Missing description field"

    def test_toolchain_defined(self, patterns_data):
        """Verify toolchain information is present"""
        assert "toolchain" in patterns_data, "Missing toolchain section"
        assert (
            "flowise" in patterns_data["toolchain"]
        ), "Missing flowise toolchain entry"
        assert (
            "mermaid_generator" in patterns_data["toolchain"]
        ), "Missing mermaid_generator toolchain entry"

    def test_all_issues_have_code_fix(self, patterns_data):
        """Verify all issues have code fix examples"""
        for issue in patterns_data["common_issues"]:
            assert "code_fix" in issue, f"Issue {issue['issue_id']} missing code_fix"
            assert (
                len(issue["code_fix"]) > 10
            ), f"Issue {issue['issue_id']} code_fix seems too short"


class TestPatternCategories:
    """Test pattern categorization"""

    @pytest.fixture
    def patterns_data(self):
        """Load flowise-expertise.json"""
        patterns_file = (
            cf_root / "extensions" / "flowise" / "patterns" / "flowise-expertise.json"
        )
        with open(patterns_file, "r") as f:
            return json.load(f)

    def test_workflow_patterns_exist(self, patterns_data):
        """Verify workflow-pattern category exists"""
        workflow_patterns = [
            p for p in patterns_data["patterns"] if p["category"] == "workflow-pattern"
        ]
        assert (
            len(workflow_patterns) >= 10
        ), f"Should have at least 10 workflow patterns, found {len(workflow_patterns)}"

    def test_issue_categories_valid(self, patterns_data):
        """Verify issue categories are valid"""
        valid_categories = [
            "node-structure",
            "output-structure",
            "architecture",
            "tool-configuration",
            "workflow-structure",
            "documentation",
            "build-process",
            "syntax",
            "performance",
        ]

        for issue in patterns_data["common_issues"]:
            assert (
                issue["category"] in valid_categories
            ), f"Issue {issue['issue_id']} has invalid category: {issue['category']}"
