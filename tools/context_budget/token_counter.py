#!/usr/bin/env python3
"""
Token Counter Utilities

Provides accurate token counting using tiktoken library with fallback heuristics.
"""

from pathlib import Path
from typing import List, Dict, Optional
import sys

# Try to import tiktoken, fall back gracefully if not available
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    print("Warning: tiktoken not available, using fallback token estimation", file=sys.stderr)


class TokenCounter:
    """Token counting utilities with tiktoken integration"""

    # Model to tiktoken encoding mapping
    ENCODINGS = {
        'claude-sonnet-4': 'cl100k_base',
        'claude-3-5-sonnet': 'cl100k_base',
        'claude-3-sonnet': 'cl100k_base',
        'claude-3-opus': 'cl100k_base',
        'claude-3-haiku': 'cl100k_base',
        'gpt-4': 'cl100k_base',
        'gpt-4-turbo': 'cl100k_base',
        'gpt-4o': 'cl100k_base',
        'gpt-3.5-turbo': 'cl100k_base',
    }

    # Context window sizes (tokens)
    CONTEXT_WINDOWS = {
        'claude-sonnet-4': 200000,
        'claude-3-5-sonnet': 200000,
        'claude-3-sonnet': 200000,
        'claude-3-opus': 200000,
        'claude-3-haiku': 200000,
        'gpt-4': 128000,
        'gpt-4-turbo': 128000,
        'gpt-4o': 128000,
        'gpt-3.5-turbo': 16385,
    }

    def __init__(self, model: str = 'claude-sonnet-4'):
        """
        Initialize token counter.

        Args:
            model: Model name (e.g., 'claude-sonnet-4', 'gpt-4')
        """
        self.model = model
        self.encoding = self._get_encoding()

    def _get_encoding(self):
        """Get tiktoken encoding for model"""
        if not TIKTOKEN_AVAILABLE:
            return None

        encoding_name = self.ENCODINGS.get(self.model, 'cl100k_base')
        try:
            return tiktoken.get_encoding(encoding_name)
        except Exception as e:
            print(f"Warning: Failed to load tiktoken encoding: {e}", file=sys.stderr)
            return None

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate tokens in text.

        Uses tiktoken if available, otherwise falls back to char_count / 4 heuristic.

        Args:
            text: Text to count tokens in

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        # Try tiktoken first
        if self.encoding is not None:
            try:
                return len(self.encoding.encode(text))
            except Exception:
                pass  # Fall through to heuristic

        # Fallback: rough heuristic (chars / 4)
        # This is ~75% accurate for English text
        return len(text) // 4

    def count_file_tokens(self, file_path: Path) -> int:
        """
        Count tokens in a file.

        Args:
            file_path: Path to file

        Returns:
            Token count in file
        """
        try:
            if isinstance(file_path, str):
                file_path = Path(file_path)

            if not file_path.exists():
                return 0

            content = file_path.read_text(encoding='utf-8', errors='ignore')
            return self.estimate_tokens(content)
        except Exception as e:
            print(f"Warning: Failed to count tokens in {file_path}: {e}", file=sys.stderr)
            return 0

    def count_message_tokens(self, messages: List[Dict]) -> int:
        """
        Count tokens in message array.

        Args:
            messages: List of message dicts with 'role' and 'content' keys

        Returns:
            Total token count in messages
        """
        total = 0
        for message in messages:
            # Count role
            role = message.get('role', '')
            total += self.estimate_tokens(role)

            # Count content
            content = message.get('content', '')
            if isinstance(content, str):
                total += self.estimate_tokens(content)
            elif isinstance(content, list):
                # Handle multi-part content (text + images)
                for part in content:
                    if isinstance(part, dict) and 'text' in part:
                        total += self.estimate_tokens(part['text'])

            # Add overhead per message (~4 tokens for formatting)
            total += 4

        return total

    def count_directory_tokens(self, directory: Path, pattern: str = "**/*.py") -> int:
        """
        Count tokens in all matching files in directory.

        Args:
            directory: Directory path
            pattern: Glob pattern (default: all Python files)

        Returns:
            Total token count
        """
        try:
            if isinstance(directory, str):
                directory = Path(directory)

            if not directory.exists():
                return 0

            total = 0
            for file_path in directory.glob(pattern):
                if file_path.is_file():
                    total += self.count_file_tokens(file_path)

            return total
        except Exception as e:
            print(f"Warning: Failed to count directory tokens: {e}", file=sys.stderr)
            return 0

    def get_context_window_size(self, model: Optional[str] = None) -> int:
        """
        Get context window size for model.

        Args:
            model: Model name (uses self.model if not provided)

        Returns:
            Context window size in tokens
        """
        model = model or self.model
        return self.CONTEXT_WINDOWS.get(model, 200000)  # Default to 200K


def estimate_tokens(text: str, model: str = 'claude-sonnet-4') -> int:
    """
    Convenience function for quick token estimation.

    Args:
        text: Text to count tokens in
        model: Model name

    Returns:
        Estimated token count
    """
    counter = TokenCounter(model)
    return counter.estimate_tokens(text)


def get_context_window_size(model: str = 'claude-sonnet-4') -> int:
    """
    Get context window size for model.

    Args:
        model: Model name

    Returns:
        Context window size in tokens
    """
    counter = TokenCounter(model)
    return counter.get_context_window_size()
