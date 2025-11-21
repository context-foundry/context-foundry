"""
Unit tests for Roblox detector

Run with: pytest extensions/roblox/tests/test_detector.py
"""

import pytest
from pathlib import Path
import json

# Add parent to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from roblox.detector import detect_roblox_project, get_project_metadata


class TestRobloxDetector:
    """Test Roblox project detection"""

    def test_detects_rojo_project(self, tmp_path):
        """Verify Rojo project detection"""
        # Create Rojo config
        config = {"name": "TestGame"}
        (tmp_path / "default.project.json").write_text(json.dumps(config))

        result = detect_roblox_project(tmp_path)

        assert result["is_roblox"] is True
        assert result["project_type"] == "roblox-game"
        assert result["project_subtype"] == "rojo"
        assert result["confidence"] == "high"

    def test_detects_placefile_project(self, tmp_path):
        """Verify placefile detection"""
        # Create placefile
        (tmp_path / "Game.rbxlx").write_text("<roblox></roblox>")

        result = detect_roblox_project(tmp_path)

        assert result["is_roblox"] is True
        assert result["project_subtype"] == "placefile"
        assert result["confidence"] == "medium"

    def test_prefers_rojo_when_both_exist(self, tmp_path):
        """When both Rojo and placefile exist, prefer Rojo"""
        # Create both
        (tmp_path / "default.project.json").write_text('{"name": "Test"}')
        (tmp_path / "Game.rbxlx").write_text("<roblox></roblox>")

        result = detect_roblox_project(tmp_path)

        assert result["project_subtype"] == "rojo"
        assert "warning" in result["metadata"]

    def test_rejects_invalid_project(self, tmp_path):
        """Verify non-detection when indicators missing"""
        # Empty directory
        result = detect_roblox_project(tmp_path)

        assert result["is_roblox"] is False

    def test_computes_has_tests_correctly(self, tmp_path):
        """Check has_tests=True when Tests/ folder exists"""
        # Create Rojo project
        (tmp_path / "default.project.json").write_text('{"name": "Test"}')

        # Create tests directory with a test file
        tests_dir = tmp_path / "src" / "ServerScriptService" / "Tests"
        tests_dir.mkdir(parents=True)
        (tests_dir / "Test.spec.lua").write_text("-- test")

        result = detect_roblox_project(tmp_path)

        assert result["has_tests"] is True

    def test_calculates_complexity(self, tmp_path):
        """Test complexity calculation"""
        # Create Rojo project
        (tmp_path / "default.project.json").write_text('{"name": "Test"}')

        # Create just a few files = simple
        src = tmp_path / "src"
        src.mkdir()
        (src / "script1.lua").write_text("-- code")
        (src / "script2.lua").write_text("-- code")

        result = detect_roblox_project(tmp_path)

        assert result["complexity"] == "simple"

    def test_detects_plugin_type(self, tmp_path):
        """Verify plugin detection"""
        (tmp_path / "default.project.json").write_text('{"name": "Test"}')
        (tmp_path / "plugin.lua").write_text("-- plugin code")

        result = detect_roblox_project(tmp_path)

        assert result["project_type"] == "roblox-plugin"

    def test_get_project_metadata(self, tmp_path):
        """Test metadata extraction"""
        # Create Rojo project with structure
        (tmp_path / "default.project.json").write_text('{"name": "Test"}')

        src = tmp_path / "src"
        (src / "ServerScriptService").mkdir(parents=True)
        (src / "ServerScriptService" / "Script.lua").write_text("-- code")

        metadata = get_project_metadata(tmp_path)

        assert metadata["has_rojo_config"] is True
        assert metadata["lua_file_count"] > 0
        assert "ServerScriptService" in metadata["directory_structure"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
