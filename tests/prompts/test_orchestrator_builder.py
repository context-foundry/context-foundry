#!/usr/bin/env python3
"""
Tests for orchestrator prompt builder.

Coverage target: 60% of build_orchestrator_prompt.py (82 statements → ~50 statements)
Priority: 8/10 - Core prompt generation
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

from prompts.build_orchestrator_prompt import build_orchestrator_prompt


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_prompt_files(tmp_path):
    """Create mock prompt component files"""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    # Create header file
    header_file = prompts_dir / "orchestrator_header.txt"
    header_file.write_text("=== HEADER CONTENT ===\n")

    # Create phase files
    phase_files = [
        "phase_0_codebase_analysis.md",
        "phase_1_scout.md",
        "phase_2_architect.md",
    ]

    for phase_file in phase_files:
        (prompts_dir / phase_file).write_text(f"=== {phase_file.upper()} ===\n")

    # Create footer file
    footer_file = prompts_dir / "orchestrator_footer.txt"
    footer_file.write_text("=== FOOTER CONTENT ===\n")

    return prompts_dir


# ============================================================================
# Basic Prompt Building Tests
# ============================================================================


@pytest.mark.tier2
@pytest.mark.unit
class TestPromptBuilder:
    """Test build_orchestrator_prompt() basic functionality"""

    def test_build_basic_prompt_returns_string(self):
        """Test that building prompt returns a string"""
        result = build_orchestrator_prompt(include_flowise=False)

        assert isinstance(result, str)
        assert len(result) > 0

    @patch("prompts.build_orchestrator_prompt.FLOWISE_AVAILABLE", True)
    def test_build_with_flowise_enabled(self):
        """Test building with Flowise enhancements"""
        result = build_orchestrator_prompt(include_flowise=True)

        assert isinstance(result, str)
        # Note: Actual Flowise content may vary, we're just testing it doesn't crash

    def test_build_with_flowise_disabled(self):
        """Test building without Flowise enhancements"""
        result = build_orchestrator_prompt(include_flowise=False)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_with_custom_output_path(self, tmp_path):
        """Test building with custom output path"""
        output_file = tmp_path / "test_prompt.txt"

        result = build_orchestrator_prompt(
            include_flowise=False, output_path=str(output_file)
        )

        assert isinstance(result, str)
        # Verify file was created
        assert output_file.exists()
        assert output_file.read_text() == result

    def test_build_prompt_contains_expected_sections(self):
        """Test that prompt contains expected major sections"""
        result = build_orchestrator_prompt(include_flowise=False)

        # Should contain key sections
        expected_keywords = [
            "PHASE",  # Phase sections
            "Scout",  # Scout phase
            "Architect",  # Architect phase
            "Builder",  # Builder phase
            "Test",  # Test phase
        ]

        for keyword in expected_keywords:
            assert keyword in result, (
                f"Expected keyword '{keyword}' not found in prompt"
            )


# ============================================================================
# Prompt Content Validation Tests
# ============================================================================


@pytest.mark.tier2
@pytest.mark.integration
class TestPromptValidation:
    """Test prompt content validation"""

    def test_all_phases_included(self):
        """Test that all phase sections are included"""
        result = build_orchestrator_prompt(include_flowise=False)

        phases = [
            "PHASE 0",  # Codebase Analysis
            "PHASE 1",  # Scout
            "PHASE 2",  # Architect
            "PHASE 3",  # Builder
            "PHASE 4",  # Test
        ]

        for phase in phases:
            assert phase in result or phase.replace(" ", "") in result.replace(
                " ", ""
            ), f"Phase '{phase}' not found in prompt"

    def test_prompt_structure_valid(self):
        """Test that prompt has valid structure (not empty sections)"""
        result = build_orchestrator_prompt(include_flowise=False)

        # Should have reasonable length
        assert len(result) > 1000, "Prompt seems too short"

        # Should not have obvious errors
        assert "ERROR" not in result.upper()
        assert "MISSING" not in result.upper()

    def test_version_info_included(self):
        """Test that version information is included"""
        result = build_orchestrator_prompt(include_flowise=False)

        # Should contain version references
        assert "version" in result.lower() or "Version" in result


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.tier3
@pytest.mark.unit
class TestPromptBuilderErrors:
    """Test error handling in prompt builder"""

    @patch("prompts.build_orchestrator_prompt.Path.exists")
    def test_missing_files_handled_gracefully(self, mock_exists):
        """Test that missing files are handled gracefully"""
        # Simulate some files missing
        mock_exists.return_value = False

        # Should still return something (fallback behavior)
        try:
            result = build_orchestrator_prompt(include_flowise=False)
            # If it doesn't raise, check result is reasonable
            assert isinstance(result, str)
        except FileNotFoundError:
            # Acceptable to raise FileNotFoundError for missing files
            pass

    def test_invalid_output_path_handled(self):
        """Test that invalid output path is handled"""
        invalid_path = "/nonexistent/directory/prompt.txt"

        try:
            result = build_orchestrator_prompt(
                include_flowise=False, output_path=invalid_path
            )
            # Should still return the prompt even if write fails
            assert isinstance(result, str)
        except (OSError, IOError, PermissionError):
            # Acceptable to raise on invalid path
            pass


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.tier2
@pytest.mark.integration
class TestPromptBuilderIntegration:
    """Integration tests for complete prompt building"""

    def test_build_and_write_complete_workflow(self, tmp_path):
        """Test complete workflow: build and write prompt"""
        output_file = tmp_path / "orchestrator_prompt.txt"

        result = build_orchestrator_prompt(
            include_flowise=False, output_path=str(output_file)
        )

        # Verify result
        assert isinstance(result, str)
        assert len(result) > 1000

        # Verify file
        assert output_file.exists()
        file_content = output_file.read_text()
        assert file_content == result
        assert len(file_content) > 1000

    def test_multiple_builds_consistent(self):
        """Test that multiple builds produce consistent output"""
        result1 = build_orchestrator_prompt(include_flowise=False)
        result2 = build_orchestrator_prompt(include_flowise=False)

        # Results should be identical (deterministic)
        assert result1 == result2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
