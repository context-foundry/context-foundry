#!/usr/bin/env python3
"""
Unit tests for use_baml.py CLI wrapper

Tests cover:
- CLI status command
- CLI update-phase command
- CLI scout-report command
- CLI architecture command
- CLI validate-build command
- Error handling and help messages
- Argument parsing and validation
"""

import sys
import json
import pytest
import subprocess
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import use_baml


class TestCLIStatus:
    """Test status command functionality"""

    @patch("tools.use_baml.is_baml_available")
    @patch("tools.use_baml.sys.argv", ["use_baml.py", "status"])
    def test_status_baml_available(self, mock_available):
        """Test status command when BAML is available"""
        mock_available.return_value = True

        # Capture output
        with patch("builtins.print") as mock_print:
            with patch("os.getenv", return_value="test_key"):
                result = use_baml.main()

        assert result == 0
        # Should print success message
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any("✅ BAML is available" in str(call) for call in print_calls)

    @patch("tools.use_baml.is_baml_available")
    @patch("tools.use_baml.get_baml_error")
    @patch("tools.use_baml.sys.argv", ["use_baml.py", "status"])
    def test_status_baml_unavailable(self, mock_error, mock_available):
        """Test status command when BAML is unavailable"""
        mock_available.return_value = False
        mock_error.return_value = "BAML not installed"

        with patch("builtins.print") as mock_print:
            result = use_baml.main()

        assert result == 1
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any("❌ BAML is not available" in str(call) for call in print_calls)


class TestCLIUpdatePhase:
    """Test update-phase command functionality"""

    @patch("tools.use_baml.update_phase_with_baml")
    @patch("tools.use_baml.clear_baml_cache")
    @patch(
        "tools.use_baml.sys.argv",
        ["use_baml.py", "update-phase", "Scout", "researching", "Test detail"],
    )
    def test_update_phase_success(self, mock_clear, mock_update):
        """Test successful phase update"""
        mock_update.return_value = {"phase": "Scout", "status": "Researching"}

        with patch("builtins.print"):
            result = use_baml.main()

        assert result == 0
        mock_clear.assert_called_once()
        mock_update.assert_called_once()

    @patch("tools.use_baml.update_phase_with_baml")
    @patch("tools.use_baml.clear_baml_cache")
    @patch(
        "tools.use_baml.sys.argv",
        [
            "use_baml.py",
            "update-phase",
            "Scout",
            "researching",
            "Test",
            "--session-id",
            "test-session",
            "--iteration",
            "2",
        ],
    )
    def test_update_phase_with_optional_args(self, mock_clear, mock_update):
        """Test phase update with session ID and iteration"""
        mock_update.return_value = {"phase": "Scout"}

        with patch("builtins.print"):
            result = use_baml.main()

        assert result == 0
        # Verify correct arguments passed
        call_args = mock_update.call_args
        assert call_args[1]["session_id"] == "test-session"
        assert call_args[1]["iteration"] == 2

    @patch("tools.use_baml.update_phase_with_baml")
    @patch("tools.use_baml.clear_baml_cache")
    def test_update_phase_status_normalization(self, mock_clear, mock_update):
        """Test that status values are normalized correctly"""
        mock_update.return_value = {"status": "Researching"}

        # Test lowercase status gets normalized
        test_cases = [
            ("researching", "Researching"),
            ("analyzing", "Analyzing"),
            ("designing", "Designing"),
            ("building", "Building"),
            ("testing", "Testing"),
            ("self-healing", "SelfHealing"),
            ("completed", "Completed"),
        ]

        for input_status, expected_status in test_cases:
            with patch(
                "tools.use_baml.sys.argv",
                ["use_baml.py", "update-phase", "Scout", input_status, "Test"],
            ):
                with patch("builtins.print"):
                    use_baml.main()

                call_args = mock_update.call_args
                assert call_args[1]["status"] == expected_status


class TestCLIScoutReport:
    """Test scout-report command functionality"""

    @patch("tools.use_baml.generate_scout_report_baml")
    @patch(
        "tools.use_baml.sys.argv",
        ["use_baml.py", "scout-report", "Build a web app", "No existing code"],
    )
    def test_scout_report_success(self, mock_scout):
        """Test successful scout report generation"""
        mock_scout.return_value = {"report": "Scout report content"}

        with patch("builtins.print"):
            result = use_baml.main()

        assert result == 0
        mock_scout.assert_called_once()

    @patch("tools.use_baml.generate_scout_report_baml")
    @patch(
        "tools.use_baml.sys.argv",
        ["use_baml.py", "scout-report", "Build app", "Code", "--patterns", "pattern1"],
    )
    def test_scout_report_with_patterns(self, mock_scout):
        """Test scout report with patterns argument"""
        mock_scout.return_value = {"report": "Content"}

        with patch("builtins.print"):
            use_baml.main()

        call_args = mock_scout.call_args
        assert call_args[1]["past_patterns"] == "pattern1"

    @patch("tools.use_baml.generate_scout_report_baml")
    @patch(
        "tools.use_baml.sys.argv", ["use_baml.py", "scout-report", "Build app", "Code"]
    )
    def test_scout_report_baml_unavailable(self, mock_scout):
        """Test scout report when BAML unavailable"""
        mock_scout.return_value = None

        with patch("builtins.print"):
            result = use_baml.main()

        assert result == 1


class TestCLIArchitecture:
    """Test architecture command functionality"""

    @patch("tools.use_baml.generate_architecture_baml")
    @patch(
        "tools.use_baml.sys.argv",
        ["use_baml.py", "architecture", '{"scout":"data"}', '["risk1","risk2"]'],
    )
    def test_architecture_success(self, mock_arch):
        """Test successful architecture generation"""
        mock_arch.return_value = {"architecture": "Arch content"}

        with patch("builtins.print"):
            result = use_baml.main()

        assert result == 0
        mock_arch.assert_called_once()

    @patch("tools.use_baml.generate_architecture_baml")
    @patch("tools.use_baml.sys.argv", ["use_baml.py", "architecture", "{}", "[]"])
    def test_architecture_baml_unavailable(self, mock_arch):
        """Test architecture when BAML unavailable"""
        mock_arch.return_value = None

        with patch("builtins.print"):
            result = use_baml.main()

        assert result == 1


class TestCLIValidateBuild:
    """Test validate-build command functionality"""

    @patch("tools.use_baml.validate_build_result_baml")
    @patch(
        "tools.use_baml.sys.argv",
        ["use_baml.py", "validate-build", '{"status":"completed"}'],
    )
    def test_validate_build_success(self, mock_validate):
        """Test successful build validation"""
        mock_validate.return_value = {"valid": True}

        with patch("builtins.print"):
            result = use_baml.main()

        assert result == 0
        mock_validate.assert_called_once()

    @patch("tools.use_baml.validate_build_result_baml")
    @patch("tools.use_baml.sys.argv", ["use_baml.py", "validate-build", "{}"])
    def test_validate_build_baml_unavailable(self, mock_validate):
        """Test build validation when BAML unavailable"""
        mock_validate.return_value = None

        with patch("builtins.print"):
            result = use_baml.main()

        assert result == 1


class TestCLIErrorHandling:
    """Test error handling and edge cases"""

    @patch("tools.use_baml.sys.argv", ["use_baml.py"])
    def test_no_command_shows_help(self):
        """Test that no command shows help and returns 1"""
        with patch("builtins.print"):
            result = use_baml.main()

        assert result == 1

    @patch("tools.use_baml.sys.argv", ["use_baml.py", "invalid-command"])
    def test_invalid_command(self):
        """Test that invalid command is handled gracefully"""
        # Should raise SystemExit from argparse
        with pytest.raises(SystemExit):
            use_baml.main()

    @patch("tools.use_baml.sys.argv", ["use_baml.py", "update-phase"])
    def test_missing_required_args(self):
        """Test that missing required arguments are caught"""
        with pytest.raises(SystemExit):
            use_baml.main()


class TestCLIIntegration:
    """Integration tests using subprocess to test actual CLI"""

    def test_cli_status_subprocess(self):
        """Test running status command via subprocess"""
        result = subprocess.run(
            [sys.executable, "tools/use_baml.py", "status"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Should complete without error (exit code 0 or 1 both acceptable)
        assert result.returncode in [0, 1]
        # Should have output
        assert len(result.stdout) > 0 or len(result.stderr) > 0

    def test_cli_help_subprocess(self):
        """Test running with --help via subprocess"""
        result = subprocess.run(
            [sys.executable, "tools/use_baml.py", "--help"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "BAML Integration CLI" in result.stdout or "usage:" in result.stdout


class TestCLIArgumentParsing:
    """Test argument parsing logic"""

    def test_status_command_no_args(self):
        """Test that status command accepts no additional args"""
        with patch("tools.use_baml.sys.argv", ["use_baml.py", "status"]):
            with patch("tools.use_baml.is_baml_available", return_value=True):
                with patch("builtins.print"):
                    with patch("os.getenv", return_value="key"):
                        result = use_baml.main()

        assert result == 0

    def test_update_phase_defaults(self):
        """Test update-phase command with default values"""
        with patch(
            "tools.use_baml.sys.argv",
            ["use_baml.py", "update-phase", "Scout", "researching", "Detail"],
        ):
            with patch("tools.use_baml.update_phase_with_baml") as mock_update:
                with patch("tools.use_baml.clear_baml_cache"):
                    mock_update.return_value = {}
                    with patch("builtins.print"):
                        use_baml.main()

            call_args = mock_update.call_args
            # Check defaults
            assert call_args[1]["session_id"] == "context-foundry"
            assert call_args[1]["iteration"] == 0


class TestCLIOutputFormat:
    """Test CLI output formatting"""

    @patch("tools.use_baml.update_phase_with_baml")
    @patch("tools.use_baml.clear_baml_cache")
    @patch(
        "tools.use_baml.sys.argv",
        ["use_baml.py", "update-phase", "Scout", "researching", "Test"],
    )
    def test_output_is_valid_json(self, mock_clear, mock_update):
        """Test that CLI output is valid JSON"""
        test_output = {"phase": "Scout", "status": "Researching"}
        mock_update.return_value = test_output

        # Capture print output
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            use_baml.main()

        output = f.getvalue()

        # Should be valid JSON
        parsed = json.loads(output.strip())
        assert parsed == test_output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
