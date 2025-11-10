#!/usr/bin/env python3
"""
Unit tests for phase_loader.py

Tests cover:
- Phase prompt loading for individual phases
- All phases loading
- Flowise mode toggling
- Error handling for invalid phases and missing files
- Phase listing functionality
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.prompts.phase_loader import (
    get_phase_prompt,
    get_all_phases,
    list_available_phases,
    PHASE_FILES,
    PHASE_NAME_MAP,
)


class TestPhasePromptLoading:
    """Test individual phase prompt loading"""

    def test_get_phase_prompt_valid_phase(self):
        """Test loading a valid phase prompt"""
        # Test loading Phase 1 (Scout)
        prompt = get_phase_prompt("1", flowise_mode=False)

        assert prompt is not None
        assert isinstance(prompt, str)
        assert len(prompt) > 100  # Should have substantial content
        assert "PHASE 1: SCOUT" in prompt or "Scout" in prompt

    def test_get_phase_prompt_all_valid_phases(self):
        """Test that all defined phases can be loaded"""
        for phase_id in PHASE_FILES.keys():
            prompt = get_phase_prompt(phase_id, flowise_mode=False)

            assert prompt is not None
            assert isinstance(prompt, str)
            assert len(prompt) > 50  # Should have content

    def test_get_phase_prompt_returns_different_content(self):
        """Test that different phases return different content"""
        phase_1 = get_phase_prompt("1", flowise_mode=False)
        phase_2 = get_phase_prompt("2", flowise_mode=False)

        assert phase_1 != phase_2
        assert len(phase_1) > 0
        assert len(phase_2) > 0


class TestPhasePromptCombined:
    """Test loading all phases combined"""

    def test_get_all_phases(self):
        """Test loading all phases concatenated"""
        all_prompts = get_all_phases(flowise_mode=False)

        assert all_prompts is not None
        assert isinstance(all_prompts, str)
        assert len(all_prompts) > 1000  # Should be substantial

    def test_get_all_phases_contains_all_phase_content(self):
        """Test that combined prompts contain individual phase content"""
        all_prompts = get_all_phases(flowise_mode=False)

        # Should contain content from multiple phases
        # Check for phase markers
        phase_count = 0
        for phase_id in ["0", "1", "2", "4", "7"]:
            individual = get_phase_prompt(phase_id, flowise_mode=False)
            # Check if individual phase content is in combined
            if individual[:100] in all_prompts:
                phase_count += 1

        assert phase_count >= 3  # At least 3 phases should be present


class TestPhasePromptFlowise:
    """Test Flowise mode functionality"""

    def test_get_phase_prompt_flowise_mode_false(self):
        """Test loading phase without Flowise enhancements"""
        prompt = get_phase_prompt("1", flowise_mode=False)

        assert prompt is not None
        assert isinstance(prompt, str)
        # Should not contain Flowise-specific markers (usually)
        # Base prompt should work

    @patch('tools.prompts.phase_loader.FLOWISE_AVAILABLE', True)
    @patch('tools.prompts.phase_loader.extensions_loader')
    def test_get_phase_prompt_flowise_mode_true(self, mock_loader):
        """Test loading phase with Flowise enhancements when available"""
        # Mock Flowise extension returning enhancement content
        mock_loader.get_extension_prompt.return_value = "FLOWISE ENHANCEMENT CONTENT"

        prompt = get_phase_prompt("1", flowise_mode=True)

        assert prompt is not None
        assert "FLOWISE ENHANCEMENT CONTENT" in prompt
        mock_loader.get_extension_prompt.assert_called()

    @patch('tools.prompts.phase_loader.FLOWISE_AVAILABLE', False)
    def test_get_phase_prompt_flowise_unavailable(self):
        """Test that Flowise mode gracefully handles unavailable Flowise"""
        # Should not crash when Flowise is unavailable
        prompt = get_phase_prompt("1", flowise_mode=True)

        assert prompt is not None
        assert isinstance(prompt, str)
        # Should return base prompt without Flowise enhancements

    def test_get_all_phases_flowise_mode(self):
        """Test loading all phases with Flowise mode"""
        all_prompts = get_all_phases(flowise_mode=True)

        assert all_prompts is not None
        assert isinstance(all_prompts, str)
        assert len(all_prompts) > 1000


class TestPhasePromptErrors:
    """Test error handling"""

    def test_get_phase_prompt_invalid_phase(self):
        """Test that invalid phase ID raises ValueError"""
        with pytest.raises(ValueError, match="Unknown phase"):
            get_phase_prompt("999", flowise_mode=False)

    def test_get_phase_prompt_empty_phase(self):
        """Test that empty phase ID raises error"""
        with pytest.raises(ValueError):
            get_phase_prompt("", flowise_mode=False)

    def test_get_phase_prompt_none_phase(self):
        """Test that None phase ID raises error"""
        with pytest.raises((ValueError, TypeError)):
            get_phase_prompt(None, flowise_mode=False)

    @patch('tools.prompts.phase_loader.PHASE_FILES', {"test": "nonexistent.md"})
    def test_get_phase_prompt_missing_file(self):
        """Test that missing phase file raises FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            get_phase_prompt("test", flowise_mode=False)


class TestPhaseListingFunctionality:
    """Test phase listing helper functions"""

    def test_list_available_phases(self):
        """Test getting list of available phases"""
        phases = list_available_phases()

        assert phases is not None
        assert isinstance(phases, list)
        assert len(phases) > 0
        assert "0" in phases
        assert "1" in phases
        assert "2" in phases
        assert "7" in phases

    def test_list_available_phases_matches_phase_files(self):
        """Test that listed phases match PHASE_FILES keys"""
        phases = list_available_phases()

        assert set(phases) == set(PHASE_FILES.keys())

    def test_phase_files_constant_valid(self):
        """Test that PHASE_FILES constant is properly defined"""
        assert PHASE_FILES is not None
        assert isinstance(PHASE_FILES, dict)
        assert len(PHASE_FILES) > 0

        # All values should be filenames ending in .md
        for phase_id, filename in PHASE_FILES.items():
            assert filename.endswith(".md")
            assert isinstance(phase_id, str)

    def test_phase_name_map_constant_valid(self):
        """Test that PHASE_NAME_MAP constant is properly defined"""
        assert PHASE_NAME_MAP is not None
        assert isinstance(PHASE_NAME_MAP, dict)
        assert len(PHASE_NAME_MAP) > 0

        # All keys should match PHASE_FILES keys
        assert set(PHASE_NAME_MAP.keys()) == set(PHASE_FILES.keys())


class TestPhasePromptContent:
    """Test phase prompt content quality"""

    def test_phase_prompts_not_empty(self):
        """Test that all phases have non-empty content"""
        for phase_id in PHASE_FILES.keys():
            prompt = get_phase_prompt(phase_id, flowise_mode=False)
            assert len(prompt.strip()) > 0

    def test_phase_prompts_contain_headers(self):
        """Test that phases contain expected formatting"""
        # Most phases should have some markdown-style formatting
        phase_1 = get_phase_prompt("1", flowise_mode=False)

        # Should contain some structure indicators
        assert any(indicator in phase_1 for indicator in ["PHASE", "##", "**", "```"])

    def test_phase_prompts_reasonable_length(self):
        """Test that phase prompts have reasonable length"""
        for phase_id in PHASE_FILES.keys():
            prompt = get_phase_prompt(phase_id, flowise_mode=False)

            # Should be at least 100 chars (non-trivial)
            assert len(prompt) >= 100, f"Phase {phase_id} too short"

            # Should be less than 100KB (reasonable)
            assert len(prompt) < 100_000, f"Phase {phase_id} too long"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
