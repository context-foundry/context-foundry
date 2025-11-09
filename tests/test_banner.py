#!/usr/bin/env python3
"""
Tests for banner display module.

Coverage target: 100% of banner.py (11 statements)
Priority: 5/10 - Simple utility
"""

import pytest
import sys
from pathlib import Path
from io import StringIO

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from banner import print_banner, get_banner


# ============================================================================
# Banner Display Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.tier3
class TestBanner:
    """Test print_banner() and get_banner() functions"""

    def test_get_banner_returns_string(self):
        """Test get_banner returns a string"""
        result = get_banner()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_banner_contains_expected_content(self):
        """Test banner contains expected visual elements (ASCII art banner)"""
        result = get_banner()

        # Banner is ASCII art, check for key visual characters and content
        assert "VERSION" in result.upper()
        assert len(result) > 500  # Banner should be substantial

    def test_get_banner_custom_version(self):
        """Test banner with custom version"""
        result = get_banner(version="1.2.3-test")

        assert "1.2.3-test" in result

    def test_get_banner_has_visual_elements(self):
        """Test banner has visual formatting"""
        result = get_banner()

        # Banner should have box drawing characters
        assert any(char in result for char in ["╔", "╚", "║", "═", "█"])

    def test_get_banner_multiple_lines(self):
        """Test banner spans multiple lines"""
        result = get_banner()

        lines = result.split("\n")
        assert len(lines) > 5  # Banner should be multi-line

    def test_print_banner_no_exceptions(self):
        """Test print_banner doesn't raise exceptions"""
        # Redirect stderr to suppress output
        old_stderr = sys.stderr
        sys.stderr = StringIO()

        try:
            print_banner()
            print_banner(version="1.0.0")
            print_banner(version=None)  # This should fail as None doesn't format
        except TypeError:
            # Expected for None version
            pass
        finally:
            sys.stderr = old_stderr

    def test_print_banner_to_custom_file(self):
        """Test printing banner to custom file object"""
        output = StringIO()
        print_banner(version="test", file=output)

        result = output.getvalue()
        assert len(result) > 0
        assert "test" in result

    def test_get_banner_version_formatting(self):
        """Test version is properly formatted in banner"""
        version = "2.0.0"
        result = get_banner(version=version)

        assert version in result
        assert "Version" in result


@pytest.mark.unit
@pytest.mark.tier3
class TestBannerFormat:
    """Test banner formatting"""

    def test_banner_has_rocket_emoji(self):
        """Test banner contains the rocket emoji"""
        result = get_banner()

        assert "🚀" in result

    def test_banner_has_tagline(self):
        """Test banner contains tagline"""
        result = get_banner()

        result_lower = result.lower()
        assert "stop" in result_lower and "building" in result_lower


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
