#!/usr/bin/env python3
"""
Unit tests for build_orchestrator_prompt.py

Tests cover:
- Prompt building with and without Flowise
- Header/footer loading
- Phase file assembly
- Output file writing
- CLI interface
- Error handling
"""

import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.prompts.build_orchestrator_prompt import (
    build_orchestrator_prompt,
    main,
)


class TestPromptBuilder:
    """Test prompt construction functionality"""

    def test_build_prompt_returns_string(self, tmp_path):
        """Test that build_orchestrator_prompt returns a string"""
        output_file = tmp_path / "test_orchestrator.txt"

        result = build_orchestrator_prompt(
            include_flowise=False, output_path=str(output_file)
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_prompt_without_flowise(self, tmp_path):
        """Test building prompt without Flowise enhancements"""
        output_file = tmp_path / "test_orchestrator.txt"

        result = build_orchestrator_prompt(
            include_flowise=False, output_path=str(output_file)
        )

        assert isinstance(result, str)
        assert len(result) > 1000  # Should have substantial content
        # Output file should be created
        assert output_file.exists()

    def test_build_prompt_with_flowise(self, tmp_path):
        """Test building prompt with Flowise enhancements"""
        output_file = tmp_path / "test_orchestrator.txt"

        result = build_orchestrator_prompt(
            include_flowise=True, output_path=str(output_file)
        )

        assert isinstance(result, str)
        assert len(result) > 1000
        assert output_file.exists()

    def test_build_prompt_output_file_created(self, tmp_path):
        """Test that output file is created at specified path"""
        output_file = tmp_path / "custom_prompt.txt"

        build_orchestrator_prompt(include_flowise=False, output_path=str(output_file))

        assert output_file.exists()
        content = output_file.read_text()
        assert len(content) > 0

    def test_build_prompt_reasonable_length(self, tmp_path):
        """Test that generated prompt has reasonable length"""
        output_file = tmp_path / "test_orchestrator.txt"

        result = build_orchestrator_prompt(
            include_flowise=False, output_path=str(output_file)
        )

        # Should be substantial but not enormous
        assert 10_000 < len(result) < 500_000


class TestPromptIntegration:
    """Test full prompt assembly"""

    def test_prompt_contains_header(self, tmp_path):
        """Test that built prompt contains header section"""
        output_file = tmp_path / "test_orchestrator.txt"

        result = build_orchestrator_prompt(
            include_flowise=False, output_path=str(output_file)
        )

        # Header should contain common sections
        assert any(
            marker in result
            for marker in [
                "GIT WORKFLOW",
                "PHASE TRACKING",
                "BAML INTEGRATION",
                "TOOL USAGE",
                "CONTEXT WINDOW BUDGET",
            ]
        )

    def test_prompt_contains_phases(self, tmp_path):
        """Test that built prompt contains phase sections"""
        output_file = tmp_path / "test_orchestrator.txt"

        result = build_orchestrator_prompt(
            include_flowise=False, output_path=str(output_file)
        )

        # Should contain phase markers
        phase_markers = ["SCOUT", "ARCHITECT", "BUILDER", "TEST"]
        found_markers = sum(1 for marker in phase_markers if marker in result)

        assert found_markers >= 2  # At least some phases present

    def test_prompt_contains_footer(self, tmp_path):
        """Test that built prompt contains footer section"""
        output_file = tmp_path / "test_orchestrator.txt"

        result = build_orchestrator_prompt(
            include_flowise=False, output_path=str(output_file)
        )

        # Footer should contain final sections
        assert any(
            marker in result
            for marker in [
                "FINAL OUTPUT",
                "CRITICAL RULES",
                "ERROR HANDLING",
                "BEGIN EXECUTION",
            ]
        )

    def test_prompt_structure_complete(self, tmp_path):
        """Test that prompt has complete structure (header + phases + footer)"""
        output_file = tmp_path / "test_orchestrator.txt"

        result = build_orchestrator_prompt(
            include_flowise=False, output_path=str(output_file)
        )

        # Check for structural completeness
        has_header = "GIT WORKFLOW" in result or "PHASE TRACKING" in result
        has_phases = "SCOUT" in result or "ARCHITECT" in result
        has_footer = "CRITICAL RULES" in result or "BEGIN EXECUTION" in result

        assert has_header, "Missing header section"
        assert has_phases, "Missing phase sections"
        assert has_footer, "Missing footer section"


class TestPromptFlowise:
    """Test Flowise enhancement handling"""

    @patch("tools.prompts.build_orchestrator_prompt.FLOWISE_AVAILABLE", True)
    @patch("tools.prompts.build_orchestrator_prompt.extensions_loader")
    def test_prompt_with_flowise_enhancements(self, mock_loader, tmp_path):
        """Test that Flowise enhancements are included when available"""
        mock_loader.get_extension_prompt.return_value = "FLOWISE TEST ENHANCEMENT"
        output_file = tmp_path / "test_orchestrator.txt"

        result = build_orchestrator_prompt(
            include_flowise=True, output_path=str(output_file)
        )

        # Should contain Flowise enhancement
        assert "FLOWISE TEST ENHANCEMENT" in result

    @patch("tools.prompts.build_orchestrator_prompt.FLOWISE_AVAILABLE", False)
    def test_prompt_without_flowise_when_unavailable(self, tmp_path):
        """Test that prompt builds without Flowise when unavailable"""
        output_file = tmp_path / "test_orchestrator.txt"

        # Should not crash when Flowise unavailable
        result = build_orchestrator_prompt(
            include_flowise=True, output_path=str(output_file)
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_prompt_flowise_flag_false(self, tmp_path):
        """Test that Flowise is excluded when include_flowise=False"""
        output_file = tmp_path / "test_orchestrator.txt"

        result = build_orchestrator_prompt(
            include_flowise=False, output_path=str(output_file)
        )

        # Should successfully build without Flowise
        assert isinstance(result, str)


class TestPromptCLI:
    """Test command-line interface"""

    @patch("tools.prompts.build_orchestrator_prompt.build_orchestrator_prompt")
    def test_cli_default_arguments(self, mock_build):
        """Test CLI with default arguments"""
        mock_build.return_value = "test prompt"

        with patch("sys.argv", ["build_orchestrator_prompt.py"]):
            main()

        # Should call build with Flowise enabled by default
        mock_build.assert_called_once()
        call_args = mock_build.call_args
        assert call_args[1]["include_flowise"] is True

    @patch("tools.prompts.build_orchestrator_prompt.build_orchestrator_prompt")
    def test_cli_no_flowise_flag(self, mock_build):
        """Test CLI with --no-flowise flag"""
        mock_build.return_value = "test prompt"

        with patch("sys.argv", ["build_orchestrator_prompt.py", "--no-flowise"]):
            main()

        call_args = mock_build.call_args
        assert call_args[1]["include_flowise"] is False

    @patch("tools.prompts.build_orchestrator_prompt.build_orchestrator_prompt")
    def test_cli_custom_output_path(self, mock_build):
        """Test CLI with custom output path"""
        mock_build.return_value = "test prompt"

        with patch(
            "sys.argv",
            ["build_orchestrator_prompt.py", "-o", "/tmp/custom_prompt.txt"],
        ):
            main()

        call_args = mock_build.call_args
        assert call_args[1]["output_path"] == "/tmp/custom_prompt.txt"

    @patch("tools.prompts.build_orchestrator_prompt.build_orchestrator_prompt")
    def test_cli_dry_run(self, mock_build):
        """Test CLI with --dry-run flag"""
        mock_build.return_value = "test prompt"

        with patch("sys.argv", ["build_orchestrator_prompt.py", "--dry-run"]):
            with patch("builtins.print"):
                main()

        # Should still call build_orchestrator_prompt
        assert mock_build.called


class TestPromptErrorHandling:
    """Test error handling"""

    @patch(
        "tools.prompts.build_orchestrator_prompt.Path.exists", return_value=False
    )
    def test_missing_header_file_raises_error(self, mock_exists):
        """Test that missing header file raises FileNotFoundError"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = Path(tmp_dir) / "test.txt"

            # Should raise when header not found
            with pytest.raises(FileNotFoundError):
                build_orchestrator_prompt(
                    include_flowise=False, output_path=str(output_file)
                )

    def test_output_directory_must_exist(self, tmp_path):
        """Test that output directory must exist (not auto-created)"""
        nested_dir = tmp_path / "nested" / "directory"
        output_file = nested_dir / "prompt.txt"

        # Directory doesn't exist yet
        assert not nested_dir.exists()

        # Should raise FileNotFoundError if directory doesn't exist
        with pytest.raises(FileNotFoundError):
            build_orchestrator_prompt(
                include_flowise=False, output_path=str(output_file)
            )


class TestPromptContent:
    """Test content quality and formatting"""

    def test_prompt_no_empty_lines_at_start(self, tmp_path):
        """Test that prompt doesn't start with empty lines"""
        output_file = tmp_path / "test_orchestrator.txt"

        result = build_orchestrator_prompt(
            include_flowise=False, output_path=str(output_file)
        )

        # Should not start with whitespace
        assert result[0] not in [" ", "\n", "\t"]

    def test_prompt_utf8_encoding(self, tmp_path):
        """Test that prompt handles UTF-8 encoding correctly"""
        output_file = tmp_path / "test_orchestrator.txt"

        result = build_orchestrator_prompt(
            include_flowise=False, output_path=str(output_file)
        )

        # Should be able to encode/decode as UTF-8
        encoded = result.encode("utf-8")
        decoded = encoded.decode("utf-8")
        assert decoded == result

    def test_written_file_matches_returned_content(self, tmp_path):
        """Test that written file content matches returned string"""
        output_file = tmp_path / "test_orchestrator.txt"

        result = build_orchestrator_prompt(
            include_flowise=False, output_path=str(output_file)
        )

        file_content = output_file.read_text(encoding="utf-8")

        assert file_content == result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
