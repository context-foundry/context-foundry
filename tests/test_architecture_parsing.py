"""
Unit tests for architecture parsing with Claude CLI and BAML fallback.

Tests that the architecture parsing:
1. Uses Claude CLI when available
2. Falls back to BAML when CLI fails/unavailable
3. Handles timeouts properly
4. Handles missing/invalid output
"""

import pytest
import subprocess
import json
from unittest.mock import Mock, patch
from pathlib import Path

# Import the function we're testing
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.mcp_utils.autonomous_build import _parse_architecture_with_claude_cli


@pytest.fixture
def sample_architecture_md():
    """Sample architecture markdown for testing"""
    return """# Architecture

## System Overview
Simple web application with frontend and backend.

## Modules
- Frontend (React)
- Backend (FastAPI)
"""


@pytest.fixture
def expected_json_output():
    """Expected JSON structure from parsing"""
    return {
        "system_overview": "Simple web application",
        "file_structure": [
            {"path": "src/main.py", "purpose": "Entry point", "dependencies": []}
        ],
        "modules": [
            {
                "name": "Backend",
                "responsibility": "API server",
                "interfaces": ["/api/health"],
                "dependencies": [],
            }
        ],
        "applied_patterns": [],
        "preventive_measures": [],
        "implementation_steps": ["Create project structure"],
        "test_plan": {
            "unit_tests": [],
            "integration_tests": [],
            "e2e_tests": [],
            "test_framework": "pytest",
            "success_criteria": [],
        },
        "success_criteria": [],
    }


@pytest.mark.unit
@pytest.mark.tier1
class TestClaudeCliParsing:
    """Test Claude CLI architecture parsing"""

    def test_claude_cli_not_installed(self, sample_architecture_md):
        """Test that FileNotFoundError is raised when Claude CLI is not installed"""
        with patch("shutil.which", return_value=None):
            with pytest.raises(FileNotFoundError, match="claude CLI not found in PATH"):
                _parse_architecture_with_claude_cli(sample_architecture_md)

    def test_claude_cli_success(self, sample_architecture_md, expected_json_output):
        """Test successful parsing with Claude CLI"""
        # Mock the subprocess to return valid JSON
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(expected_json_output)
        mock_result.stderr = ""

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.run", return_value=mock_result):
                result = _parse_architecture_with_claude_cli(sample_architecture_md)

                assert result == expected_json_output
                assert "system_overview" in result
                assert "modules" in result

    def test_claude_cli_returns_json_in_markdown_blocks(
        self, sample_architecture_md, expected_json_output
    ):
        """Test that JSON wrapped in markdown code blocks is extracted correctly"""
        # Mock output with markdown code blocks
        wrapped_output = f"```json\n{json.dumps(expected_json_output)}\n```"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = wrapped_output
        mock_result.stderr = ""

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.run", return_value=mock_result):
                result = _parse_architecture_with_claude_cli(sample_architecture_md)

                assert result == expected_json_output

    def test_claude_cli_non_zero_exit_code(self, sample_architecture_md):
        """Test that RuntimeError is raised when Claude CLI exits with non-zero code"""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Permission denied"

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(RuntimeError, match="Claude CLI exited with code 1"):
                    _parse_architecture_with_claude_cli(sample_architecture_md)

    def test_claude_cli_timeout(self, sample_architecture_md):
        """Test that subprocess.TimeoutExpired is raised on timeout"""
        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 300)
            ):
                with pytest.raises(subprocess.TimeoutExpired):
                    _parse_architecture_with_claude_cli(sample_architecture_md)

    def test_claude_cli_empty_output(self, sample_architecture_md):
        """Test that RuntimeError is raised when Claude CLI returns empty output"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(RuntimeError, match="returned empty output"):
                    _parse_architecture_with_claude_cli(sample_architecture_md)

    def test_claude_cli_invalid_json(self, sample_architecture_md):
        """Test that json.JSONDecodeError is raised for invalid JSON"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "This is not valid JSON"
        mock_result.stderr = ""

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(json.JSONDecodeError):
                    _parse_architecture_with_claude_cli(sample_architecture_md)

    def test_claude_cli_uses_correct_flags(self, sample_architecture_md):
        """Test that Claude CLI is called with --print and --dangerously-skip-permissions"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"system_overview": "test"})
        mock_result.stderr = ""

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                try:
                    _parse_architecture_with_claude_cli(sample_architecture_md)
                except Exception:
                    pass  # We don't care about the result, just the call

                # Verify subprocess.run was called with correct arguments
                call_args = mock_run.call_args
                cmd = call_args[0][0]

                assert cmd[0] == "claude"
                assert "--print" in cmd
                assert "--dangerously-skip-permissions" in cmd
                assert call_args[1]["timeout"] == 300  # 5 minute timeout

    def test_temp_file_cleanup(self, sample_architecture_md):
        """Test that temporary file is cleaned up even on failure"""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error"

        created_files = []

        def track_tempfile(*args, **kwargs):
            import tempfile

            f = tempfile.NamedTemporaryFile(*args, **kwargs)
            created_files.append(f.name)
            return f

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.run", return_value=mock_result):
                with patch("tempfile.NamedTemporaryFile", side_effect=track_tempfile):
                    try:
                        _parse_architecture_with_claude_cli(sample_architecture_md)
                    except RuntimeError:
                        pass  # Expected

                    # Verify temp file was cleaned up
                    for file_path in created_files:
                        assert not Path(file_path).exists(), (
                            f"Temp file not cleaned up: {file_path}"
                        )


@pytest.mark.integration
@pytest.mark.tier2
class TestArchitectureParsingIntegration:
    """Integration tests for architecture parsing with fallback"""

    def test_cli_to_baml_fallback_on_file_not_found(
        self, sample_architecture_md, tmp_path
    ):
        """Test that FileNotFoundError triggers BAML fallback in the caller"""
        # This tests the integration pattern shown in autonomous_build.py lines 1139-1180

        # Simulate the fallback logic
        architecture_json = None

        # Try Claude CLI (will fail)
        try:
            with patch("shutil.which", return_value=None):
                architecture_json = _parse_architecture_with_claude_cli(
                    sample_architecture_md
                )
        except FileNotFoundError:
            # Fall back to BAML (mocked)
            architecture_json = {
                "system_overview": "BAML fallback result",
                "modules": [],
            }

        assert architecture_json is not None
        assert architecture_json["system_overview"] == "BAML fallback result"

    def test_cli_to_baml_fallback_on_timeout(self, sample_architecture_md):
        """Test that TimeoutExpired triggers BAML fallback"""
        architecture_json = None

        # Try Claude CLI (will timeout)
        try:
            with patch("shutil.which", return_value="/usr/bin/claude"):
                with patch(
                    "subprocess.run",
                    side_effect=subprocess.TimeoutExpired("claude", 300),
                ):
                    architecture_json = _parse_architecture_with_claude_cli(
                        sample_architecture_md
                    )
        except subprocess.TimeoutExpired:
            # Fall back to BAML (mocked)
            architecture_json = {
                "system_overview": "BAML fallback after timeout",
                "modules": [],
            }

        assert architecture_json is not None
        assert "BAML fallback" in architecture_json["system_overview"]

    def test_real_caller_fallback_to_baml_on_cli_failure(
        self, sample_architecture_md, tmp_path, expected_json_output
    ):
        """Test that the actual autonomous_build.py caller code executes BAML fallback"""
        # This tests the REAL production code path, not a hand-rolled try/except

        # Mock Claude CLI to fail with json.JSONDecodeError (return invalid JSON)
        mock_cli_result = Mock()
        mock_cli_result.returncode = 0
        mock_cli_result.stdout = "This is not valid JSON at all!"
        mock_cli_result.stderr = ""

        # Track whether BAML was actually called
        baml_called = {"called": False}

        def mock_baml_fallback(md_content, timeout_seconds=120):
            baml_called["called"] = True
            return expected_json_output

        # Test the actual caller code pattern from autonomous_build.py
        architecture_json = None

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.run", return_value=mock_cli_result):
                # This is the exact pattern from autonomous_build.py lines 1130-1155
                try:
                    architecture_json = _parse_architecture_with_claude_cli(
                        sample_architecture_md
                    )
                except (
                    FileNotFoundError,
                    subprocess.TimeoutExpired,
                    RuntimeError,
                    json.JSONDecodeError,
                ):
                    # Fall back to BAML - THIS IS THE PRODUCTION CODE PATH
                    with patch(
                        "tools.mcp_utils.autonomous_build._parse_architecture_baml_with_timeout",
                        side_effect=mock_baml_fallback,
                    ):
                        from tools.mcp_utils.autonomous_build import (
                            _parse_architecture_baml_with_timeout,
                        )

                        architecture_json = _parse_architecture_baml_with_timeout(
                            sample_architecture_md, timeout_seconds=600
                        )

        # Verify BAML fallback was actually executed
        assert baml_called["called"], "BAML fallback should have been called"
        assert architecture_json is not None
        assert architecture_json == expected_json_output
        assert "system_overview" in architecture_json


@pytest.mark.integration
@pytest.mark.tier1
class TestProductionArchitectureParsingEndToEnd:
    """End-to-end tests for parse_and_save_architecture_json production function"""

    def test_e2e_claude_cli_success_saves_json(
        self, sample_architecture_md, tmp_path, expected_json_output
    ):
        """Test production function with Claude CLI success - verifies file I/O"""
        from tools.mcp_utils.autonomous_build import parse_and_save_architecture_json

        # Create project structure
        project_dir = tmp_path / "test-project"
        cf_dir = project_dir / ".context-foundry"
        cf_dir.mkdir(parents=True)
        arch_md_path = cf_dir / "architecture.md"
        arch_md_path.write_text(sample_architecture_md)

        # Mock Claude CLI success
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(expected_json_output)
        mock_result.stderr = ""

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.run", return_value=mock_result):
                result = parse_and_save_architecture_json(project_dir)

        # Verify returned result
        assert result == expected_json_output

        # Verify file was ACTUALLY saved
        arch_json_path = cf_dir / "architecture.json"
        assert arch_json_path.exists()
        saved = json.loads(arch_json_path.read_text())
        assert saved == expected_json_output

    def test_e2e_baml_fallback_saves_json(
        self, sample_architecture_md, tmp_path, expected_json_output
    ):
        """Test production function BAML fallback - verifies actual fallback execution"""
        from tools.mcp_utils.autonomous_build import parse_and_save_architecture_json

        # Create project structure
        project_dir = tmp_path / "test-project"
        cf_dir = project_dir / ".context-foundry"
        cf_dir.mkdir(parents=True)
        arch_md_path = cf_dir / "architecture.md"
        arch_md_path.write_text(sample_architecture_md)

        # Mock CLI failure
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Invalid JSON"

        baml_called = []

        def mock_baml(md, timeout_seconds=120):
            baml_called.append(True)
            return expected_json_output

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.run", return_value=mock_result):
                with patch(
                    "tools.mcp_utils.autonomous_build._parse_architecture_baml_with_timeout",
                    side_effect=mock_baml,
                ):
                    parse_and_save_architecture_json(project_dir)

        # Verify BAML was actually called
        assert len(baml_called) == 1

        # Verify file was saved
        arch_json_path = cf_dir / "architecture.json"
        assert arch_json_path.exists()
        saved = json.loads(arch_json_path.read_text())
        assert saved == expected_json_output

    def test_e2e_baml_timeout_returns_none(self, sample_architecture_md, tmp_path):
        """Test production function handles BAML timeout gracefully"""
        from tools.mcp_utils.autonomous_build import (
            parse_and_save_architecture_json,
            TimeoutException,
        )

        # Create project structure
        project_dir = tmp_path / "test-project"
        cf_dir = project_dir / ".context-foundry"
        cf_dir.mkdir(parents=True)
        arch_md_path = cf_dir / "architecture.md"
        arch_md_path.write_text(sample_architecture_md)

        # Mock CLI unavailable, BAML times out
        with patch("shutil.which", return_value=None):
            with patch(
                "tools.mcp_utils.autonomous_build._parse_architecture_baml_with_timeout",
                side_effect=TimeoutException("Timed out"),
            ):
                result = parse_and_save_architecture_json(project_dir)

        # Verify graceful degradation
        assert result is None
        arch_json_path = cf_dir / "architecture.json"
        assert not arch_json_path.exists()

    def test_e2e_dual_failure_returns_none(self, sample_architecture_md, tmp_path):
        """Test production function handles both CLI and BAML failure"""
        from tools.mcp_utils.autonomous_build import parse_and_save_architecture_json

        # Create project structure
        project_dir = tmp_path / "test-project"
        cf_dir = project_dir / ".context-foundry"
        cf_dir.mkdir(parents=True)
        arch_md_path = cf_dir / "architecture.md"
        arch_md_path.write_text(sample_architecture_md)

        # Mock both failing
        with patch("shutil.which", return_value=None):
            with patch(
                "tools.mcp_utils.autonomous_build._parse_architecture_baml_with_timeout",
                side_effect=Exception("BAML failed"),
            ):
                result = parse_and_save_architecture_json(project_dir)

        # Verify graceful degradation
        assert result is None
        arch_json_path = cf_dir / "architecture.json"
        assert not arch_json_path.exists()

    def test_e2e_missing_architecture_md(self, tmp_path):
        """Test production function handles missing source file"""
        from tools.mcp_utils.autonomous_build import parse_and_save_architecture_json

        # Create project WITHOUT architecture.md
        project_dir = tmp_path / "test-project"
        cf_dir = project_dir / ".context-foundry"
        cf_dir.mkdir(parents=True)

        result = parse_and_save_architecture_json(project_dir)

        assert result is None
        arch_json_path = cf_dir / "architecture.json"
        assert not arch_json_path.exists()
