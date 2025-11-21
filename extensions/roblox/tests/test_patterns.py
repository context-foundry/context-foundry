"""
Unit tests for Roblox patterns loading

Run with: pytest extensions/roblox/tests/test_patterns.py
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from roblox.extensions_loader import load_extension_patterns, load_extension_detectors


class TestRobloxPatterns:
    """Test pattern loading"""

    def test_loads_patterns(self):
        """Verify pattern JSON loads without errors"""
        patterns = load_extension_patterns("roblox-expertise")

        assert patterns is not None
        assert "patterns" in patterns
        assert len(patterns["patterns"]) > 0

    def test_obby_pattern_structure(self):
        """Verify obby pattern has required fields"""
        patterns = load_extension_patterns("roblox-expertise")

        # Find obby pattern
        obby_pattern = None
        for pattern in patterns["patterns"]:
            if pattern["pattern_id"] == "obby-checkpoints-coin-shop":
                obby_pattern = pattern
                break

        assert obby_pattern is not None
        assert "required_systems" in obby_pattern
        assert "directory_layout" in obby_pattern
        assert "code_templates" in obby_pattern
        assert "security_requirements" in obby_pattern

    def test_common_issues_present(self):
        """Verify common issues are defined"""
        patterns = load_extension_patterns("roblox-expertise")

        assert "common_issues" in patterns
        assert len(patterns["common_issues"]) > 0

        # Check for security issue
        security_issue = None
        for issue in patterns["common_issues"]:
            if "remote" in issue["issue_id"].lower():
                security_issue = issue
                break

        assert security_issue is not None
        assert security_issue["severity"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_detector_loads(self):
        """Test detector module loads correctly"""
        detectors = load_extension_detectors()

        assert "roblox" in detectors
        assert hasattr(detectors["roblox"], "detect_roblox_project")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
