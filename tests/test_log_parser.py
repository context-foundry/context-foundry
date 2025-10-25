#!/usr/bin/env python3
"""
Test suite for LogParser module
20+ test cases with sample logs
"""

import pytest
from tools.metrics.log_parser import LogParser, TokenUsage, parse_usage_string


class TestLogParser:
    """Test LogParser functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        self.parser = LogParser()

    def test_parse_api_response_json(self):
        """Test parsing standard Claude API JSON response"""
        log_line = '''{"id": "msg_123", "type": "message", "usage": {"input_tokens": 1250, "output_tokens": 580, "cache_read_input_tokens": 940}}'''

        usage = self.parser.parse_api_response(log_line)

        assert usage is not None
        assert usage.input_tokens == 1250
        assert usage.output_tokens == 580
        assert usage.cache_read_tokens == 940
        assert usage.request_id == "msg_123"

    def test_parse_api_response_with_cache_write(self):
        """Test parsing response with cache write tokens"""
        log_line = '''{"usage": {"input_tokens": 500, "output_tokens": 200, "cache_creation_input_tokens": 300, "cache_read_input_tokens": 100}}'''

        usage = self.parser.parse_api_response(log_line)

        assert usage is not None
        assert usage.input_tokens == 500
        assert usage.output_tokens == 200
        assert usage.cache_write_tokens == 300
        assert usage.cache_read_tokens == 100

    def test_parse_legacy_format(self):
        """Test parsing legacy text format"""
        log_line = "Input tokens: 1250, Output tokens: 580"

        usage = self.parser.parse_legacy_format(log_line)

        assert usage is not None
        assert usage.input_tokens == 1250
        assert usage.output_tokens == 580

    def test_parse_legacy_with_cache(self):
        """Test parsing legacy format with cache tokens"""
        log_line = "Input tokens: 1000, Output tokens: 500, Cache read tokens: 2000"

        usage = self.parser.parse_legacy_format(log_line)

        assert usage is not None
        assert usage.input_tokens == 1000
        assert usage.output_tokens == 500
        assert usage.cache_read_tokens == 2000

    def test_parse_malformed_json(self):
        """Test handling malformed JSON"""
        log_line = '''{"usage": {"input_tokens": 500, "output_tok'''

        usage = self.parser.parse_api_response(log_line)

        assert usage is None

    def test_parse_missing_usage_field(self):
        """Test handling JSON without usage field"""
        log_line = '''{"id": "msg_123", "type": "message"}'''

        usage = self.parser.parse_api_response(log_line)

        assert usage is None

    def test_parse_zero_tokens(self):
        """Test handling zero token counts"""
        log_line = '''{"usage": {"input_tokens": 0, "output_tokens": 0}}'''

        usage = self.parser.parse_api_response(log_line)

        assert usage is not None
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0

    def test_parse_large_token_counts(self):
        """Test handling large token counts"""
        log_line = '''{"usage": {"input_tokens": 195000, "output_tokens": 4500}}'''

        usage = self.parser.parse_api_response(log_line)

        assert usage is not None
        assert usage.input_tokens == 195000
        assert usage.output_tokens == 4500
        assert usage.total_tokens == 199500

    def test_parse_with_model_info(self):
        """Test extracting model information"""
        log_line = '''{"id": "msg_123", "model": "claude-sonnet-4-20250514", "usage": {"input_tokens": 1000, "output_tokens": 500}}'''

        usage = self.parser.parse_api_response(log_line)

        assert usage is not None
        assert usage.model == "claude-sonnet-4-20250514"

    def test_parse_empty_string(self):
        """Test handling empty string"""
        usage = self.parser.parse_api_response("")

        assert usage is None

    def test_parse_non_json_text(self):
        """Test handling non-JSON text"""
        usage = self.parser.parse_api_response("This is just regular text")

        assert usage is None

    def test_parse_unicode_handling(self):
        """Test handling Unicode characters in logs"""
        log_line = '''{"id": "msg_123", "usage": {"input_tokens": 1000, "output_tokens": 500}, "content": "Hello 世界"}'''

        usage = self.parser.parse_api_response(log_line)

        assert usage is not None
        assert usage.input_tokens == 1000

    def test_total_tokens_calculation(self):
        """Test total tokens property calculation"""
        usage = TokenUsage(
            input_tokens=1250,
            output_tokens=580,
            cache_read_tokens=940
        )

        assert usage.total_tokens == 1830

    def test_to_dict_conversion(self):
        """Test TokenUsage to dict conversion"""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=200,
            request_id="msg_123"
        )

        result = usage.to_dict()

        assert result['input_tokens'] == 1000
        assert result['output_tokens'] == 500
        assert result['cache_read_tokens'] == 200
        assert result['total_tokens'] == 1500
        assert result['request_id'] == "msg_123"

    def test_calculate_latency(self):
        """Test latency calculation"""
        start = "2025-01-13T10:00:00"
        end = "2025-01-13T10:00:02.500"

        latency = self.parser.calculate_latency(start, end)

        assert latency == 2500  # 2.5 seconds = 2500ms

    def test_calculate_latency_zero(self):
        """Test latency calculation with same timestamps"""
        timestamp = "2025-01-13T10:00:00"

        latency = self.parser.calculate_latency(timestamp, timestamp)

        assert latency == 0

    def test_calculate_latency_invalid(self):
        """Test latency calculation with invalid timestamps"""
        latency = self.parser.calculate_latency("invalid", "also invalid")

        assert latency == 0  # Should return 0 on error

    def test_parse_multiple_responses_in_stream(self):
        """Test parsing multiple API responses from stream"""
        lines = [
            '{"usage": {"input_tokens": 1000, "output_tokens": 500}}',
            'Some other log line',
            '{"usage": {"input_tokens": 2000, "output_tokens": 800}}',
        ]

        results = list(self.parser.parse_stream(lines))

        assert len(results) == 2
        assert results[0].input_tokens == 1000
        assert results[1].input_tokens == 2000

    def test_parse_stream_with_legacy_format(self):
        """Test parsing stream with mixed formats"""
        lines = [
            '{"usage": {"input_tokens": 1000, "output_tokens": 500}}',
            'Input tokens: 1250, Output tokens: 580',
        ]

        results = list(self.parser.parse_stream(lines))

        assert len(results) == 2
        assert results[0].input_tokens == 1000
        assert results[1].input_tokens == 1250

    def test_parse_stream_empty(self):
        """Test parsing empty stream"""
        results = list(self.parser.parse_stream([]))

        assert len(results) == 0

    def test_parse_usage_string_utility(self):
        """Test parse_usage_string utility function"""
        usage = parse_usage_string('{"usage": {"input_tokens": 1500, "output_tokens": 750}}')

        assert usage is not None
        assert usage.input_tokens == 1500
        assert usage.output_tokens == 750

    def test_parse_nested_json_block(self):
        """Test parsing nested JSON with usage field"""
        log_line = '''
        {
            "id": "msg_456",
            "type": "message",
            "role": "assistant",
            "usage": {
                "input_tokens": 3000,
                "output_tokens": 1500,
                "cache_read_input_tokens": 5000
            },
            "content": [{"type": "text", "text": "Response"}]
        }
        '''

        usage = self.parser.parse_api_response(log_line)

        assert usage is not None
        assert usage.input_tokens == 3000
        assert usage.output_tokens == 1500
        assert usage.cache_read_tokens == 5000

    def test_parse_with_timestamp_extraction(self):
        """Test timestamp extraction from logs"""
        log_line = '2025-01-13T10:30:00 {"usage": {"input_tokens": 1000, "output_tokens": 500}}'

        usage = self.parser.parse_api_response(log_line)

        assert usage is not None
        assert usage.timestamp == "2025-01-13T10:30:00"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
