"""
Tests for Extensions Loader
"""

import unittest
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import extensions_loader


class TestExtensionsLoader(unittest.TestCase):
    """Test cases for extensions loader."""

    def test_load_detectors_success(self):
        """Test loading detectors when extension exists."""
        detectors = extensions_loader.load_extension_detectors()

        # When running from the extension itself, should load successfully
        if detectors is not None:
            self.assertIsInstance(detectors, dict)
            self.assertIn("flowise", detectors)
            self.assertTrue(hasattr(detectors["flowise"], "detect_flowise_flow"))

    def test_load_detectors_returns_none_or_dict(self):
        """Test that load_detectors returns None or dict, never raises."""
        result = extensions_loader.load_extension_detectors()
        self.assertTrue(result is None or isinstance(result, dict))

    def test_load_patterns_flowise(self):
        """Test loading Flowise patterns."""
        patterns = extensions_loader.load_extension_patterns("flowise")

        # May return None if pattern files don't exist, or dict if they do
        if patterns is not None:
            self.assertIsInstance(patterns, dict)
            # Example files have .example extension
            # Either patterns or empty dict is acceptable

    def test_load_patterns_invalid_extension(self):
        """Test loading patterns for non-existent extension."""
        patterns = extensions_loader.load_extension_patterns("nonexistent")
        self.assertIsNone(patterns)

    def test_get_extension_prompt_scout(self):
        """Test loading Scout phase prompt."""
        prompt = extensions_loader.get_extension_prompt("flowise", "scout")

        # May return None if prompt doesn't exist, or string if it does
        if prompt is not None:
            self.assertIsInstance(prompt, str)
            self.assertGreater(len(prompt), 0)

    def test_get_extension_prompt_architect(self):
        """Test loading Architect phase prompt."""
        prompt = extensions_loader.get_extension_prompt("flowise", "architect")

        # May return None or string
        if prompt is not None:
            self.assertIsInstance(prompt, str)
            self.assertGreater(len(prompt), 0)

    def test_get_extension_prompt_invalid_extension(self):
        """Test loading prompt for non-existent extension."""
        prompt = extensions_loader.get_extension_prompt("nonexistent", "scout")
        self.assertIsNone(prompt)

    def test_get_extension_prompt_invalid_phase(self):
        """Test loading prompt for non-existent phase."""
        prompt = extensions_loader.get_extension_prompt("flowise", "nonexistent")
        self.assertIsNone(prompt)

    def test_extension_exists(self):
        """Test checking if extension exists."""
        # When running from extension directory, should exist
        exists = extensions_loader.extension_exists("flowise")
        self.assertIsInstance(exists, bool)

    def test_extension_exists_invalid(self):
        """Test checking non-existent extension."""
        exists = extensions_loader.extension_exists("nonexistent")
        self.assertFalse(exists)

    def test_get_available_extensions(self):
        """Test getting list of available extensions."""
        extensions = extensions_loader.get_available_extensions()

        self.assertIsInstance(extensions, list)
        # When running from flowise extension, should be in list
        # Otherwise, list may be empty

    def test_load_flow_templates(self):
        """Test loading flow templates catalog."""
        templates = extensions_loader.load_flow_templates()

        # May return None if template files don't exist
        if templates is not None:
            self.assertIsInstance(templates, dict)

    def test_graceful_none_returns(self):
        """Test that all functions handle missing files gracefully."""
        # None of these should raise exceptions
        try:
            extensions_loader.load_extension_detectors()
            extensions_loader.load_extension_patterns("flowise")
            extensions_loader.get_extension_prompt("flowise", "scout")
            extensions_loader.extension_exists("flowise")
            extensions_loader.get_available_extensions()
            extensions_loader.load_flow_templates()

            # If we get here, no exceptions were raised - good!
            self.assertTrue(True)

        except Exception as e:
            self.fail(f"Extension loader raised exception: {e}")

    def test_detector_import_returns_valid_module(self):
        """Test that loaded detector has expected functions."""
        detectors = extensions_loader.load_extension_detectors()

        if detectors and "flowise" in detectors:
            detector_module = detectors["flowise"]

            # Check for required functions
            self.assertTrue(hasattr(detector_module, "detect_flowise_flow"))
            self.assertTrue(callable(detector_module.detect_flowise_flow))

            self.assertTrue(hasattr(detector_module, "scan_directory"))
            self.assertTrue(callable(detector_module.scan_directory))

            self.assertTrue(hasattr(detector_module, "classify_flow_type"))
            self.assertTrue(callable(detector_module.classify_flow_type))


class TestLoaderErrorHandling(unittest.TestCase):
    """Test error handling in loader."""

    def test_no_exceptions_on_missing_files(self):
        """Verify loader never raises exceptions for missing files."""
        # These should all return None, never raise
        result1 = extensions_loader.get_extension_prompt("flowise", "nonexistent_phase")
        result2 = extensions_loader.load_extension_patterns("flowise")

        # Both should be None or valid data, never an exception
        self.assertTrue(result1 is None or isinstance(result1, str))
        self.assertTrue(result2 is None or isinstance(result2, dict))


if __name__ == "__main__":
    unittest.main()
