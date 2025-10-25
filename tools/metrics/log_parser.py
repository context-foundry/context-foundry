#!/usr/bin/env python3
"""
Log Parser Module
Extract token usage and metrics from Claude API logs
"""

import re
import json
from typing import Optional, Dict, Any, Generator
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TokenUsage:
    """Token usage data from API response"""
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    request_id: Optional[str] = None
    timestamp: Optional[str] = None
    model: Optional[str] = None

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output, excluding cache)"""
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'cache_read_tokens': self.cache_read_tokens,
            'cache_write_tokens': self.cache_write_tokens,
            'total_tokens': self.total_tokens,
            'request_id': self.request_id,
            'timestamp': self.timestamp,
            'model': self.model
        }


@dataclass
class APICallMetrics:
    """Complete API call metrics including timing"""
    usage: TokenUsage
    latency_ms: Optional[int] = None
    request_start: Optional[str] = None
    request_end: Optional[str] = None


class LogParser:
    """Parse Claude API logs for token usage and metrics"""

    # Regex patterns for different log formats
    JSON_BLOCK_PATTERN = re.compile(r'\{[^}]*"usage"[^}]*\}', re.DOTALL)
    USAGE_FIELD_PATTERN = re.compile(r'"usage"\s*:\s*(\{[^}]+\})')
    TOKEN_PATTERN = re.compile(r'"(\w+_tokens)"\s*:\s*(\d+)')
    REQUEST_ID_PATTERN = re.compile(r'"id"\s*:\s*"([^"]+)"')
    MODEL_PATTERN = re.compile(r'"model"\s*:\s*"([^"]+)"')

    # Legacy text format patterns
    LEGACY_INPUT_PATTERN = re.compile(r'input[_\s]tokens?:\s*(\d+)', re.IGNORECASE)
    LEGACY_OUTPUT_PATTERN = re.compile(r'output[_\s]tokens?:\s*(\d+)', re.IGNORECASE)
    LEGACY_CACHE_PATTERN = re.compile(r'cache[_\s]read[_\s]tokens?:\s*(\d+)', re.IGNORECASE)

    # Timestamp pattern
    TIMESTAMP_PATTERN = re.compile(r'(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})')

    def __init__(self):
        """Initialize log parser"""
        self._request_timestamps = {}  # Track request timing

    def parse_stream(self, lines) -> Generator[TokenUsage, None, None]:
        """
        Parse log stream line-by-line.

        Args:
            lines: Iterator of log lines (from subprocess.stdout.readline())

        Yields:
            TokenUsage objects for each API call found
        """
        for line in lines:
            if not line:
                continue

            # Handle both str and bytes
            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='ignore')

            line = line.strip()

            if not line:
                continue

            # Try single-line JSON parsing first
            usage = self.parse_api_response(line)
            if usage:
                yield usage
            else:
                # Try legacy format
                usage = self.parse_legacy_format(line)
                if usage:
                    yield usage

    def parse_api_response(self, line: str) -> Optional[TokenUsage]:
        """
        Extract token usage from API response JSON.

        Args:
            line: Log line containing JSON response

        Returns:
            TokenUsage object or None if not found
        """
        try:
            # Try direct JSON parsing first
            if line.strip().startswith('{'):
                data = json.loads(line)
                if 'usage' in data:
                    return self._extract_usage_from_dict(data)

            # Try regex extraction
            usage_match = self.USAGE_FIELD_PATTERN.search(line)
            if usage_match:
                usage_json = usage_match.group(1)
                usage_data = json.loads(usage_json)

                # Extract from main response if available
                try:
                    full_data = json.loads(line)
                    request_id = full_data.get('id')
                    model = full_data.get('model')
                except:
                    request_id = None
                    model = None

                return TokenUsage(
                    input_tokens=usage_data.get('input_tokens', 0),
                    output_tokens=usage_data.get('output_tokens', 0),
                    cache_read_tokens=usage_data.get('cache_read_input_tokens', 0),
                    cache_write_tokens=usage_data.get('cache_creation_input_tokens', 0),
                    request_id=request_id,
                    model=model,
                    timestamp=self._extract_timestamp(line)
                )

        except (json.JSONDecodeError, KeyError, ValueError):
            pass

        return None

    def _extract_usage_from_dict(self, data: Dict) -> Optional[TokenUsage]:
        """Extract usage from parsed JSON dict"""
        if 'usage' not in data:
            return None

        usage = data['usage']

        return TokenUsage(
            input_tokens=usage.get('input_tokens', 0),
            output_tokens=usage.get('output_tokens', 0),
            cache_read_tokens=usage.get('cache_read_input_tokens', 0),
            cache_write_tokens=usage.get('cache_creation_input_tokens', 0),
            request_id=data.get('id'),
            model=data.get('model'),
            timestamp=self._extract_timestamp(str(data))
        )

    def parse_legacy_format(self, line: str) -> Optional[TokenUsage]:
        """
        Parse legacy text format (non-JSON).

        Example: "Input tokens: 1250, Output tokens: 580"

        Args:
            line: Log line in text format

        Returns:
            TokenUsage object or None
        """
        input_match = self.LEGACY_INPUT_PATTERN.search(line)
        output_match = self.LEGACY_OUTPUT_PATTERN.search(line)

        if input_match or output_match:
            input_tokens = int(input_match.group(1)) if input_match else 0
            output_tokens = int(output_match.group(1)) if output_match else 0

            cache_match = self.LEGACY_CACHE_PATTERN.search(line)
            cache_tokens = int(cache_match.group(1)) if cache_match else 0

            return TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_tokens,
                cache_write_tokens=0,
                timestamp=self._extract_timestamp(line)
            )

        return None

    def _extract_timestamp(self, text: str) -> Optional[str]:
        """Extract ISO timestamp from text"""
        match = self.TIMESTAMP_PATTERN.search(text)
        if match:
            return match.group(1)
        return None

    def calculate_latency(self, request_start: str, response_end: str) -> int:
        """
        Calculate API call latency in milliseconds.

        Args:
            request_start: ISO timestamp of request start
            response_end: ISO timestamp of response end

        Returns:
            Latency in milliseconds
        """
        try:
            # Parse timestamps
            start = datetime.fromisoformat(request_start.replace('Z', '+00:00'))
            end = datetime.fromisoformat(response_end.replace('Z', '+00:00'))

            # Calculate difference
            delta = end - start
            latency_ms = int(delta.total_seconds() * 1000)

            return max(0, latency_ms)  # Ensure non-negative
        except (ValueError, AttributeError):
            return 0

    def parse_subprocess_output(self, process, timeout: Optional[float] = None) -> Generator[TokenUsage, None, None]:
        """
        Parse subprocess output in real-time.

        Args:
            process: subprocess.Popen object
            timeout: Optional timeout in seconds

        Yields:
            TokenUsage objects as they're found
        """
        import time
        start_time = time.time()

        while True:
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                break

            # Read line (non-blocking)
            line = process.stdout.readline()

            if not line and process.poll() is not None:
                # Process finished
                break

            if line:
                line = line.strip()
                # Try to parse
                usage = self.parse_api_response(line)
                if usage:
                    yield usage
                else:
                    usage = self.parse_legacy_format(line)
                    if usage:
                        yield usage

    def parse_log_file(self, file_path: str) -> Generator[TokenUsage, None, None]:
        """
        Parse existing log file.

        Args:
            file_path: Path to log file

        Yields:
            TokenUsage objects found in file
        """
        with open(file_path, 'r') as f:
            for line in f:
                usage = self.parse_api_response(line)
                if usage:
                    yield usage
                else:
                    usage = self.parse_legacy_format(line)
                    if usage:
                        yield usage


def parse_usage_string(usage_str: str) -> Optional[TokenUsage]:
    """
    Utility function to parse token usage from string.

    Args:
        usage_str: String containing token usage info

    Returns:
        TokenUsage object or None
    """
    parser = LogParser()

    # Try JSON first
    usage = parser.parse_api_response(usage_str)
    if usage:
        return usage

    # Try legacy format
    return parser.parse_legacy_format(usage_str)
