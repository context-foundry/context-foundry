#!/usr/bin/env python3
"""
Unit Tests for Cached Prompt Builder
"""

import unittest
import json
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.prompts.cached_prompt_builder import (
    build_cached_prompt,
    _build_standard_prompt,
    _estimate_tokens,
    count_prompt_tokens,
    get_prompt_hash,
    validate_cache_markers
)
from tools.prompts import CacheConfig


class TestCachedPromptBuilder(unittest.TestCase):
    """Test suite for cached prompt builder"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_config = {
            "task": "Build a test application",
            "working_directory": "/tmp/test",
            "mode": "new_project",
            "enable_test_loop": True,
            "max_test_iterations": 3
        }

        # Create temporary orchestrator prompt for testing
        self.temp_prompt_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.txt',
            delete=False
        )

        # Write test prompt with cache boundary
        # Need at least 1024 tokens (~4096 characters minimum)
        test_prompt_content = """YOU ARE A TEST ORCHESTRATOR

This is the static section with instructions.
It contains phase descriptions and workflows.

More static content here...
""" + "Static line with more content to reach minimum token count for caching validation.\n" * 80 + """
<<CACHE_BOUNDARY_MARKER>>

Dynamic content will be injected here.
"""

        self.temp_prompt_file.write(test_prompt_content)
        self.temp_prompt_file.close()
        self.temp_prompt_path = self.temp_prompt_file.name

    def tearDown(self):
        """Clean up test fixtures"""
        Path(self.temp_prompt_path).unlink(missing_ok=True)

    def test_build_cached_prompt_with_caching_enabled(self):
        """Test building prompt with caching enabled"""
        prompt = build_cached_prompt(
            self.test_config,
            orchestrator_prompt_path=self.temp_prompt_path,
            enable_caching=True
        )

        # Should contain cache marker
        self.assertIn("ANTHROPIC_CACHE_CONTROL", prompt)

        # Should contain task configuration
        self.assertIn("AUTONOMOUS BUILD TASK", prompt)
        self.assertIn('"task": "Build a test application"', prompt)

        # Should contain static content
        self.assertIn("TEST ORCHESTRATOR", prompt)

    def test_build_cached_prompt_with_caching_disabled(self):
        """Test building prompt with caching disabled"""
        prompt = build_cached_prompt(
            self.test_config,
            orchestrator_prompt_path=self.temp_prompt_path,
            enable_caching=False
        )

        # Should NOT contain cache marker
        self.assertNotIn("ANTHROPIC_CACHE_CONTROL", prompt)

        # Should still contain task configuration
        self.assertIn("AUTONOMOUS BUILD TASK", prompt)
        self.assertIn('"task": "Build a test application"', prompt)

    def test_build_standard_prompt(self):
        """Test standard prompt building (fallback)"""
        prompt = _build_standard_prompt(
            self.test_config,
            self.temp_prompt_path
        )

        # Should not contain cache markers
        self.assertNotIn("ANTHROPIC_CACHE_CONTROL", prompt)
        self.assertNotIn("<<CACHE_BOUNDARY_MARKER>>", prompt)

        # Should contain task config
        self.assertIn("AUTONOMOUS BUILD TASK", prompt)

    def test_estimate_tokens(self):
        """Test token estimation"""
        # Test with known text
        text = "This is a test string with multiple words"
        tokens = _estimate_tokens(text)

        # Should be roughly chars/4
        expected = len(text) // 4
        self.assertEqual(tokens, expected)

    def test_token_counting(self):
        """Test accurate token counting (if anthropic available)"""
        text = "Hello world, this is a test."
        tokens = count_prompt_tokens(text)

        # Should return a positive integer
        self.assertGreater(tokens, 0)
        self.assertIsInstance(tokens, int)

    def test_get_prompt_hash(self):
        """Test prompt hash generation"""
        prompt1 = "This is a test prompt"
        prompt2 = "This is a different prompt"

        hash1 = get_prompt_hash(prompt1)
        hash2 = get_prompt_hash(prompt2)

        # Hashes should be different
        self.assertNotEqual(hash1, hash2)

        # Hash should be 12 characters
        self.assertEqual(len(hash1), 12)
        self.assertEqual(len(hash2), 12)

        # Same prompt should produce same hash
        hash1_again = get_prompt_hash(prompt1)
        self.assertEqual(hash1, hash1_again)

    def test_validate_cache_markers_valid(self):
        """Test cache marker validation with valid prompt"""
        prompt = """Static content here

<!-- ANTHROPIC_CACHE_CONTROL: {"type": "ephemeral"} -->

AUTONOMOUS BUILD TASK

Configuration here...
"""

        result = validate_cache_markers(prompt)

        self.assertTrue(result['valid'])
        self.assertTrue(result['has_marker'])
        self.assertEqual(result['marker_count'], 1)
        self.assertGreater(result['marker_position'], 0)
        self.assertEqual(len(result['issues']), 0)

    def test_validate_cache_markers_missing(self):
        """Test cache marker validation with missing marker"""
        prompt = """Static content here

AUTONOMOUS BUILD TASK

Configuration here...
"""

        result = validate_cache_markers(prompt)

        self.assertFalse(result['valid'])
        self.assertFalse(result['has_marker'])
        self.assertEqual(result['marker_count'], 0)
        self.assertGreater(len(result['issues']), 0)

    def test_validate_cache_markers_multiple(self):
        """Test cache marker validation with multiple markers"""
        prompt = """Static content here

<!-- ANTHROPIC_CACHE_CONTROL: {"type": "ephemeral"} -->

More content

<!-- ANTHROPIC_CACHE_CONTROL: {"type": "ephemeral"} -->

AUTONOMOUS BUILD TASK
"""

        result = validate_cache_markers(prompt)

        self.assertFalse(result['valid'])
        self.assertTrue(result['has_marker'])
        self.assertEqual(result['marker_count'], 2)
        self.assertIn("Multiple cache markers", result['issues'][0])

    def test_cache_boundary_detection(self):
        """Test that cache boundary is correctly detected"""
        prompt = build_cached_prompt(
            self.test_config,
            orchestrator_prompt_path=self.temp_prompt_path,
            enable_caching=True
        )

        # Find the cache marker position
        marker_pos = prompt.find("ANTHROPIC_CACHE_CONTROL")
        task_pos = prompt.find("AUTONOMOUS BUILD TASK")

        # Marker should come before task section
        self.assertGreater(marker_pos, 0)
        self.assertGreater(task_pos, marker_pos)

    def test_cache_ttl_configuration(self):
        """Test cache TTL configuration"""
        # Test with 5m TTL
        prompt_5m = build_cached_prompt(
            self.test_config,
            orchestrator_prompt_path=self.temp_prompt_path,
            enable_caching=True,
            cache_ttl="5m"
        )

        self.assertIn('"ttl": "5m"', prompt_5m)

        # Test with 1h TTL
        prompt_1h = build_cached_prompt(
            self.test_config,
            orchestrator_prompt_path=self.temp_prompt_path,
            enable_caching=True,
            cache_ttl="1h"
        )

        self.assertIn('"ttl": "1h"', prompt_1h)

    def test_task_config_embedding(self):
        """Test that task configuration is properly embedded"""
        prompt = build_cached_prompt(
            self.test_config,
            orchestrator_prompt_path=self.temp_prompt_path,
            enable_caching=True
        )

        # Check all config fields are present
        self.assertIn('"task": "Build a test application"', prompt)
        self.assertIn('"working_directory": "/tmp/test"', prompt)
        self.assertIn('"mode": "new_project"', prompt)
        self.assertIn('"enable_test_loop": true', prompt)
        self.assertIn('"max_test_iterations": 3', prompt)

    def test_file_not_found_error(self):
        """Test error handling for missing prompt file"""
        with self.assertRaises(FileNotFoundError):
            build_cached_prompt(
                self.test_config,
                orchestrator_prompt_path="/nonexistent/path/prompt.txt",
                enable_caching=True
            )


class TestCacheConfig(unittest.TestCase):
    """Test suite for CacheConfig class"""

    def test_default_config_loading(self):
        """Test loading default configuration"""
        # Create temp config
        temp_config = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        )

        config_data = {
            "version": "1.0.0",
            "caching": {
                "enabled": True,
                "ttl": "5m",
                "min_tokens": 1024,
                "models_supported": ["claude-sonnet-4"]
            },
            "metrics": {
                "track_cache_hits": True
            }
        }

        json.dump(config_data, temp_config)
        temp_config.close()

        # Load config
        config = CacheConfig(temp_config.name)

        self.assertTrue(config.is_caching_enabled())
        self.assertEqual(config.get_cache_ttl(), "5m")
        self.assertEqual(config.get_min_tokens(), 1024)
        self.assertTrue(config.should_track_cache_hits())

        # Clean up
        Path(temp_config.name).unlink()

    def test_model_support_check(self):
        """Test model support checking"""
        temp_config = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        )

        config_data = {
            "caching": {
                "models_supported": ["claude-sonnet-4", "claude-opus-4"]
            }
        }

        json.dump(config_data, temp_config)
        temp_config.close()

        config = CacheConfig(temp_config.name)

        # Supported models
        self.assertTrue(config.is_model_supported("claude-sonnet-4-20250514"))
        self.assertTrue(config.is_model_supported("claude-opus-4-20250514"))

        # Unsupported models
        self.assertFalse(config.is_model_supported("gpt-4-turbo"))

        # Clean up
        Path(temp_config.name).unlink()

    def test_enable_disable_caching(self):
        """Test enabling and disabling caching"""
        temp_config = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        )

        config_data = {"caching": {"enabled": True}}
        json.dump(config_data, temp_config)
        temp_config.close()

        config = CacheConfig(temp_config.name)

        # Initially enabled
        self.assertTrue(config.is_caching_enabled())

        # Disable
        config.disable_caching()
        self.assertFalse(config.is_caching_enabled())

        # Enable
        config.enable_caching()
        self.assertTrue(config.is_caching_enabled())

        # Clean up
        Path(temp_config.name).unlink()


if __name__ == '__main__':
    unittest.main()
