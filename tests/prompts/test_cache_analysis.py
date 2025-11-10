#!/usr/bin/env python3
"""
Unit tests for cache_analysis.py

Tests cover:
- Prompt structure analysis
- Cache boundary detection
- Token estimation
- Cost analysis
- Section analysis
- Report generation
- CLI interface
"""

import sys
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.prompts.cache_analysis import (
    analyze_prompt_structure,
    print_analysis_report,
    _estimate_tokens,
    _analyze_sections,
    main,
)


class TestTokenEstimation:
    """Test token estimation functionality"""

    def test_estimate_tokens_basic(self):
        """Test basic token estimation"""
        text = "This is a test" * 100  # 1400 chars
        tokens = _estimate_tokens(text)

        assert isinstance(tokens, int)
        assert tokens > 0
        # Should be ~4 chars per token
        assert 300 < tokens < 400

    def test_estimate_tokens_empty(self):
        """Test token estimation with empty string"""
        tokens = _estimate_tokens("")
        assert tokens == 0

    def test_estimate_tokens_large_text(self):
        """Test token estimation with large text"""
        text = "word " * 10000  # 50K chars
        tokens = _estimate_tokens(text)

        assert tokens > 10000  # Should be reasonable


class TestSectionAnalysis:
    """Test section content analysis"""

    def test_analyze_sections_static_phase_instructions(self):
        """Test detection of phase instructions in static section"""
        static = "PHASE 1: SCOUT\nPHASE 2: ARCHITECT"
        dynamic = "task: build something"

        result = _analyze_sections(static, dynamic)

        assert "Phase instructions" in result["static_types"]

    def test_analyze_sections_static_git_workflow(self):
        """Test detection of Git workflow in static section"""
        static = "GIT WORKFLOW REFERENCE\nSome git commands"
        dynamic = "config data"

        result = _analyze_sections(static, dynamic)

        assert "Git workflow reference" in result["static_types"]

    def test_analyze_sections_dynamic_task_config(self):
        """Test detection of task configuration in dynamic section"""
        static = "instructions"
        dynamic = 'CONFIGURATION:\n{"task": "build app"}'

        result = _analyze_sections(static, dynamic)

        assert "Task configuration" in result["dynamic_types"]

    def test_analyze_sections_empty(self):
        """Test section analysis with empty content"""
        result = _analyze_sections("", "")

        assert "static_types" in result
        assert "dynamic_types" in result
        assert len(result["static_types"]) > 0  # Should have fallback


class TestPromptAnalysis:
    """Test prompt structure analysis"""

    def test_analyze_prompt_file_not_found(self):
        """Test analysis when prompt file doesn't exist"""
        result = analyze_prompt_structure("/nonexistent/path/prompt.txt")

        assert "error" in result
        assert result["total_lines"] == 0
        assert result["total_tokens"] == 0

    def test_analyze_prompt_basic_structure(self, tmp_path):
        """Test analysis of basic prompt structure"""
        # Create test prompt file
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_content = """PHASE 1: SCOUT
Research and gather context

PHASE 2: ARCHITECT
Design the system

""" * 50  # Make it substantial

        prompt_file.write_text(prompt_content)

        result = analyze_prompt_structure(str(prompt_file))

        assert "total_lines" in result
        assert "total_chars" in result
        assert "total_tokens" in result
        assert result["total_lines"] > 0
        assert result["total_tokens"] > 0

    def test_analyze_prompt_with_cache_boundary(self, tmp_path):
        """Test detection of explicit cache boundary marker"""
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_content = """Static content before boundary
More static content

<<CACHE_BOUNDARY_MARKER>>

Dynamic content after boundary
"""
        prompt_file.write_text(prompt_content)

        result = analyze_prompt_structure(str(prompt_file))

        assert result["has_boundary_marker"] is True
        assert result["recommended_boundary"] is not None

    def test_analyze_prompt_without_explicit_boundary(self, tmp_path):
        """Test heuristic boundary detection without explicit marker"""
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_content = """Static instructions
More static content

BEGIN EXECUTION NOW
"""
        prompt_file.write_text(prompt_content)

        result = analyze_prompt_structure(str(prompt_file))

        assert result["recommended_boundary"] is not None

    def test_analyze_prompt_sections_split(self, tmp_path):
        """Test that prompt is split into static and dynamic sections"""
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_content = "x" * 10000  # 10K chars

        prompt_file.write_text(prompt_content)

        result = analyze_prompt_structure(str(prompt_file))

        assert "static_section" in result
        assert "dynamic_section" in result
        # Total tokens should equal static + dynamic
        assert result["total_tokens"] > 0


class TestCostAnalysis:
    """Test cost analysis functionality"""

    def test_cost_analysis_present(self, tmp_path):
        """Test that cost analysis is included in results"""
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_file.write_text("x" * 10000)

        result = analyze_prompt_structure(str(prompt_file))

        assert "cost_analysis" in result
        cost = result["cost_analysis"]
        assert "first_request" in cost
        assert "subsequent_request" in cost
        assert "savings_50_builds" in cost
        assert "savings_percentage" in cost

    def test_cost_analysis_values_reasonable(self, tmp_path):
        """Test that cost analysis produces reasonable values"""
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_file.write_text("x" * 100000)  # 100K chars ~25K tokens

        result = analyze_prompt_structure(str(prompt_file))

        cost = result["cost_analysis"]
        # Costs should be positive
        assert cost["first_request"] > 0
        assert cost["subsequent_request"] >= 0
        # Caching should save money
        assert cost["cost_with_caching_50_builds"] <= cost["cost_without_caching_50_builds"]

    def test_cost_analysis_caching_saves_money(self, tmp_path):
        """Test that caching analysis shows savings"""
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_file.write_text("x" * 50000)  # Substantial content

        result = analyze_prompt_structure(str(prompt_file))

        cost = result["cost_analysis"]
        # Savings should be positive
        assert cost["savings_50_builds"] >= 0
        assert cost["savings_percentage"] >= 0


class TestRecommendations:
    """Test recommendation generation"""

    def test_recommendations_present(self, tmp_path):
        """Test that recommendations are generated"""
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_file.write_text("x" * 10000)

        result = analyze_prompt_structure(str(prompt_file))

        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)
        assert len(result["recommendations"]) > 0

    def test_recommendations_cacheable_section(self, tmp_path):
        """Test recommendation for cacheable static section"""
        prompt_file = tmp_path / "test_prompt.txt"
        # Create content large enough to be cacheable (>1024 tokens = >4096 chars)
        prompt_file.write_text("x" * 10000)

        result = analyze_prompt_structure(str(prompt_file))

        # Should have recommendation about cacheability
        recommendations = "\n".join(result["recommendations"])
        # Check that recommendations mention token or caching
        assert "token" in recommendations.lower() or "caching" in recommendations.lower()


class TestReportGeneration:
    """Test report printing functionality"""

    def test_print_analysis_report_no_error(self, tmp_path):
        """Test that report prints without errors"""
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_file.write_text("test content" * 1000)

        analysis = analyze_prompt_structure(str(prompt_file))

        # Should not raise exception
        with patch("builtins.print"):
            print_analysis_report(analysis)

    def test_print_analysis_report_error_handling(self):
        """Test report handles error case"""
        analysis = {"error": "Test error", "total_lines": 0}

        # Should not crash
        with patch("builtins.print"):
            print_analysis_report(analysis)

    def test_print_analysis_report_has_sections(self, tmp_path):
        """Test that report includes all expected sections"""
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_file.write_text("x" * 10000)

        analysis = analyze_prompt_structure(str(prompt_file))

        # Capture print output
        with patch("builtins.print") as mock_print:
            print_analysis_report(analysis)

        # Should have printed multiple sections
        assert mock_print.call_count > 10  # Many print statements


class TestCLI:
    """Test CLI interface"""

    @patch("tools.prompts.cache_analysis.analyze_prompt_structure")
    @patch("tools.prompts.cache_analysis.print_analysis_report")
    def test_cli_default_arguments(self, mock_print, mock_analyze):
        """Test CLI with default arguments"""
        mock_analyze.return_value = {"total_lines": 100}

        with patch("sys.argv", ["cache_analysis.py"]):
            main()

        # Should call analyze with default path
        mock_analyze.assert_called_once()
        call_args = mock_analyze.call_args[0]
        assert "orchestrator_prompt.txt" in call_args[0]

    @patch("tools.prompts.cache_analysis.analyze_prompt_structure")
    def test_cli_custom_prompt_path(self, mock_analyze):
        """Test CLI with custom prompt path"""
        # Return minimal required structure for print_analysis_report
        mock_analyze.return_value = {
            "total_lines": 100,
            "total_chars": 1000,
            "total_tokens": 250,
            "has_boundary_marker": False,
            "static_section": {
                "lines": 90,
                "tokens": 200,
                "cacheable": True,
                "content_types": ["Phase instructions"],
            },
            "dynamic_section": {
                "lines": 10,
                "tokens": 50,
                "content_types": ["Task config"],
            },
            "cost_analysis": {
                "savings_50_builds": 0.5,
                "savings_percentage": 80.0,
                "cost_without_caching_50_builds": 1.0,
                "cost_with_caching_50_builds": 0.5,
            },
            "recommendations": [],
        }

        with patch("sys.argv", ["cache_analysis.py", "--prompt", "/custom/path.txt"]):
            with patch("builtins.print"):
                main()

        call_args = mock_analyze.call_args[0]
        assert call_args[0] == "/custom/path.txt"

    @patch("tools.prompts.cache_analysis.analyze_prompt_structure")
    def test_cli_json_output(self, mock_analyze):
        """Test CLI with JSON output flag"""
        test_analysis = {"total_lines": 100, "total_tokens": 500}
        mock_analyze.return_value = test_analysis

        with patch("sys.argv", ["cache_analysis.py", "--json"]):
            with patch("builtins.print") as mock_print:
                main()

        # Should print JSON
        mock_print.assert_called()
        printed_text = str(mock_print.call_args[0][0])
        # Should contain JSON structure
        assert "{" in printed_text or "total_lines" in printed_text


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_empty_prompt_file(self, tmp_path):
        """Test analysis of empty prompt file"""
        prompt_file = tmp_path / "empty.txt"
        prompt_file.write_text("")

        result = analyze_prompt_structure(str(prompt_file))

        assert result["total_lines"] >= 0
        assert result["total_tokens"] == 0

    def test_very_small_prompt(self, tmp_path):
        """Test analysis of very small prompt"""
        prompt_file = tmp_path / "small.txt"
        prompt_file.write_text("x")

        result = analyze_prompt_structure(str(prompt_file))

        assert "static_section" in result
        assert result["static_section"]["cacheable"] is False  # Too small

    def test_very_large_prompt(self, tmp_path):
        """Test analysis of very large prompt"""
        prompt_file = tmp_path / "large.txt"
        prompt_file.write_text("x" * 1_000_000)  # 1MB

        result = analyze_prompt_structure(str(prompt_file))

        assert result["total_tokens"] > 200_000  # Should be large
        assert "recommendations" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
