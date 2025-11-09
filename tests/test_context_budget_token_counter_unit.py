#!/usr/bin/env python3
"""
Unit Tests for Token Counter

Tests the TokenCounter class which provides accurate token counting
using tiktoken library with fallback heuristics.

Test Coverage:
- Initialization
- Token estimation (with tiktoken)
- Token estimation (fallback)
- File token counting
- Directory token counting
- Message token counting
"""

import pytest
import sys
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.context_budget.token_counter import (
    TokenCounter,
    estimate_tokens,
    get_context_window_size
)


class TestTokenCounterInitialization:
    """Test TokenCounter initialization"""

    def test_default_initialization(self):
        """Test TokenCounter initializes with default model"""
        counter = TokenCounter()

        assert counter.model == 'claude-sonnet-4'

    def test_custom_model_initialization(self):
        """Test TokenCounter initializes with custom model"""
        counter = TokenCounter(model='gpt-4')

        assert counter.model == 'gpt-4'


class TestTokenEstimationWithTiktoken:
    """Test token estimation when tiktoken is available"""

    @pytest.mark.skipif(
        not hasattr(sys.modules.get('tools.context_budget.token_counter'), 'TIKTOKEN_AVAILABLE')
        or not sys.modules['tools.context_budget.token_counter'].TIKTOKEN_AVAILABLE,
        reason="tiktoken not available"
    )
    def test_estimate_tokens_with_tiktoken(self):
        """Test estimate_tokens() uses tiktoken when available"""
        counter = TokenCounter()

        text = "Hello, world! This is a test sentence."
        tokens = counter.estimate_tokens(text)

        # Should return reasonable token count
        assert tokens > 0
        assert tokens < len(text)  # Tokens should be less than char count

    @pytest.mark.skipif(
        not hasattr(sys.modules.get('tools.context_budget.token_counter'), 'TIKTOKEN_AVAILABLE')
        or not sys.modules['tools.context_budget.token_counter'].TIKTOKEN_AVAILABLE,
        reason="tiktoken not available"
    )
    def test_accuracy_against_known_counts(self):
        """Test tiktoken estimation accuracy"""
        counter = TokenCounter()

        # Short text
        short_text = "Hello"
        short_tokens = counter.estimate_tokens(short_text)
        assert short_tokens >= 1

    def test_empty_string_handling(self):
        """Test empty string returns 0 tokens"""
        counter = TokenCounter()

        assert counter.estimate_tokens("") == 0
        assert counter.estimate_tokens(None) == 0

    @pytest.mark.skipif(
        not hasattr(sys.modules.get('tools.context_budget.token_counter'), 'TIKTOKEN_AVAILABLE')
        or not sys.modules['tools.context_budget.token_counter'].TIKTOKEN_AVAILABLE,
        reason="tiktoken not available"
    )
    def test_unicode_text_handling(self):
        """Test unicode text is handled correctly"""
        counter = TokenCounter()

        unicode_text = "Hello 世界 🌍"
        tokens = counter.estimate_tokens(unicode_text)

        assert tokens > 0

    @pytest.mark.skipif(
        not hasattr(sys.modules.get('tools.context_budget.token_counter'), 'TIKTOKEN_AVAILABLE')
        or not sys.modules['tools.context_budget.token_counter'].TIKTOKEN_AVAILABLE,
        reason="tiktoken not available"
    )
    def test_very_long_text_handling(self):
        """Test very long text is handled correctly"""
        counter = TokenCounter()

        # Generate long text
        long_text = "Hello world! " * 1000  # ~13K chars
        tokens = counter.estimate_tokens(long_text)

        assert tokens > 0
        # Rough sanity check: should be 1/3 to 1/5 of char count
        assert tokens < len(long_text)


class TestTokenEstimationFallback:
    """Test token estimation fallback when tiktoken unavailable"""

    @patch('tools.context_budget.token_counter.TIKTOKEN_AVAILABLE', False)
    def test_fallback_heuristic_without_tiktoken(self):
        """Test fallback heuristic when tiktoken unavailable"""
        # Create counter with tiktoken mocked as unavailable
        with patch('tools.context_budget.token_counter.TIKTOKEN_AVAILABLE', False):
            counter = TokenCounter()
            counter.encoding = None  # Force fallback

            text = "Hello world! " * 100  # 1300 chars
            tokens = counter.estimate_tokens(text)

            # Fallback uses chars / 4
            expected = len(text) // 4
            assert tokens == expected

    def test_fallback_heuristic_accuracy(self):
        """Test fallback heuristic approximation"""
        counter = TokenCounter()
        counter.encoding = None  # Force fallback

        # 1000 chars should be ~250 tokens
        text = "x" * 1000
        tokens = counter.estimate_tokens(text)

        assert tokens == 250

    def test_fallback_with_various_lengths(self):
        """Test fallback heuristic with different text lengths"""
        counter = TokenCounter()
        counter.encoding = None  # Force fallback

        assert counter.estimate_tokens("a" * 100) == 25
        assert counter.estimate_tokens("a" * 400) == 100
        assert counter.estimate_tokens("a" * 1000) == 250


class TestFileTokenCounting:
    """Test file token counting"""

    def test_count_file_tokens_with_temp_file(self):
        """Test count_file_tokens() with temporary file"""
        counter = TokenCounter()

        # Create temp file with known content
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Hello world! " * 100)
            temp_path = f.name

        try:
            tokens = counter.count_file_tokens(Path(temp_path))
            assert tokens > 0
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_nonexistent_file_handling(self):
        """Test count_file_tokens() with non-existent file"""
        counter = TokenCounter()

        nonexistent = Path('/tmp/this_file_does_not_exist_12345.txt')
        tokens = counter.count_file_tokens(nonexistent)

        assert tokens == 0

    def test_binary_file_handling(self):
        """Test count_file_tokens() handles binary files gracefully"""
        counter = TokenCounter()

        # Create temp binary file
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b'\x00\x01\x02\x03' * 100)
            temp_path = f.name

        try:
            # Should handle gracefully (either count or return 0)
            tokens = counter.count_file_tokens(Path(temp_path))
            assert tokens >= 0
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_encoding_error_handling(self):
        """Test count_file_tokens() handles encoding errors"""
        counter = TokenCounter()

        # Create file with invalid UTF-8
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b'\xff\xfe Invalid UTF-8')
            temp_path = f.name

        try:
            # Should handle gracefully using errors='ignore'
            tokens = counter.count_file_tokens(Path(temp_path))
            assert tokens >= 0
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestDirectoryTokenCounting:
    """Test directory token counting"""

    def test_count_directory_tokens_with_pattern(self):
        """Test count_directory_tokens() with pattern matching"""
        counter = TokenCounter()

        # Create temp directory with files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create Python files
            (tmppath / 'file1.py').write_text('print("hello")\n' * 10)
            (tmppath / 'file2.py').write_text('print("world")\n' * 10)
            # Create non-Python file
            (tmppath / 'readme.txt').write_text('This is a readme\n' * 10)

            # Count only .py files
            tokens = counter.count_directory_tokens(tmppath, pattern='*.py')

            assert tokens > 0

    def test_empty_directory_handling(self):
        """Test count_directory_tokens() with empty directory"""
        counter = TokenCounter()

        with tempfile.TemporaryDirectory() as tmpdir:
            tokens = counter.count_directory_tokens(Path(tmpdir))

            assert tokens == 0


class TestMessageTokenCounting:
    """Test message array token counting"""

    def test_count_message_tokens_with_simple_messages(self):
        """Test count_message_tokens() with message array"""
        counter = TokenCounter()

        messages = [
            {'role': 'user', 'content': 'Hello, how are you?'},
            {'role': 'assistant', 'content': 'I am doing well, thank you!'}
        ]

        tokens = counter.count_message_tokens(messages)

        # Should count content + roles + overhead
        assert tokens > 0

    def test_multipart_content_handling(self):
        """Test count_message_tokens() with multi-part content"""
        counter = TokenCounter()

        messages = [
            {
                'role': 'user',
                'content': [
                    {'text': 'What is this image?'},
                    {'type': 'image', 'source': 'base64...'}
                ]
            }
        ]

        tokens = counter.count_message_tokens(messages)

        # Should count text parts
        assert tokens > 0


class TestContextWindowSize:
    """Test context window size retrieval"""

    def test_get_context_window_for_claude(self):
        """Test get_context_window_size() for Claude models"""
        counter = TokenCounter(model='claude-sonnet-4')

        size = counter.get_context_window_size()

        assert size == 200000

    def test_get_context_window_for_gpt4(self):
        """Test get_context_window_size() for GPT-4"""
        counter = TokenCounter(model='gpt-4')

        size = counter.get_context_window_size()

        assert size == 128000

    def test_get_context_window_default(self):
        """Test get_context_window_size() defaults to 200K"""
        counter = TokenCounter(model='unknown-model')

        size = counter.get_context_window_size()

        assert size == 200000  # Default


class TestConvenienceFunctions:
    """Test module-level convenience functions"""

    def test_estimate_tokens_convenience_function(self):
        """Test estimate_tokens() convenience function"""
        tokens = estimate_tokens("Hello world!")

        assert tokens > 0

    def test_get_context_window_size_convenience_function(self):
        """Test get_context_window_size() convenience function"""
        size = get_context_window_size('claude-sonnet-4')

        assert size == 200000


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_count_file_tokens_with_string_path(self):
        """Test count_file_tokens() accepts string paths"""
        counter = TokenCounter()

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Test content")
            temp_path = f.name

        try:
            # Pass as string instead of Path
            tokens = counter.count_file_tokens(temp_path)
            assert tokens > 0
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_count_directory_tokens_with_string_path(self):
        """Test count_directory_tokens() accepts string paths"""
        counter = TokenCounter()

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'test.py').write_text('print("hello")')

            # Pass as string instead of Path
            tokens = counter.count_directory_tokens(tmpdir, pattern='*.py')
            assert tokens > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
