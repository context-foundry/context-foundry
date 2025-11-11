"""
Log parsers for MCP Log Monitor
Parses various log formats (MCP JSON-RPC, Context Foundry, etc.)
"""

import re
import json
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class TokenUsage:
    """Token usage information"""

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LogEntry:
    """Parsed log entry"""

    timestamp: str
    server: str
    level: str  # INFO, WARNING, ERROR
    message: str
    raw: str
    structured_data: Optional[Dict[str, Any]] = None
    tokens: Optional[TokenUsage] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        if self.tokens:
            result["tokens"] = asdict(self.tokens)
        return result


class MCPLogParser:
    """Parse MCP JSON-RPC log messages"""

    # Regex patterns
    JSON_PATTERN = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")
    TIMESTAMP_PATTERN = re.compile(
        r"(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z)?)"
    )

    def parse_line(self, line: str, server: str) -> Optional[LogEntry]:
        """
        Parse a single log line.

        Args:
            line: Raw log line
            server: Server name

        Returns:
            LogEntry if parseable, None otherwise
        """
        # Extract timestamp
        timestamp_match = self.TIMESTAMP_PATTERN.search(line)
        timestamp = (
            timestamp_match.group(1)
            if timestamp_match
            else datetime.utcnow().isoformat()
        )

        # Try to find JSON content
        json_match = self.JSON_PATTERN.search(line)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                return self._parse_json_data(data, line, server, timestamp)
            except json.JSONDecodeError:
                pass

        # Fallback to text parsing
        return self._parse_text(line, server, timestamp)

    def _parse_json_data(
        self, data: Dict, raw: str, server: str, timestamp: str
    ) -> LogEntry:
        """Parse JSON log data"""
        level = "INFO"
        message = ""
        structured_data = data
        tokens = None

        # Check for MCP tool call
        if data.get("method") == "tools/call":
            params = data.get("params", {})
            tool_name = params.get("name", "unknown")
            message = f"Tool call: {tool_name}"
            level = "INFO"

        # Check for MCP notification
        elif "method" in data and data.get("method").startswith("notifications/"):
            message = f"Notification: {data.get('method')}"
            level = "INFO"

        # Check for token usage
        elif "usage" in data:
            usage = data["usage"]
            tokens = TokenUsage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_read_tokens=usage.get("cache_read_tokens", 0),
                cache_write_tokens=usage.get("cache_write_tokens", 0),
            )
            message = f"Token usage: {tokens.total_tokens} tokens"
            level = "INFO"

        # Check for error
        elif "error" in data:
            error = data["error"]
            message = f"Error: {error.get('message', 'Unknown error')}"
            level = "ERROR"

        # Generic JSON
        else:
            message = str(data)[:100]  # Truncate long messages
            level = "INFO"

        return LogEntry(
            timestamp=timestamp,
            server=server,
            level=level,
            message=message,
            raw=raw,
            structured_data=structured_data,
            tokens=tokens,
        )

    def _parse_text(self, line: str, server: str, timestamp: str) -> LogEntry:
        """Parse plain text log line"""
        level = "INFO"

        # Detect log level
        line_upper = line.upper()
        if "ERROR" in line_upper or "FAIL" in line_upper:
            level = "ERROR"
        elif "WARN" in line_upper:
            level = "WARNING"

        return LogEntry(
            timestamp=timestamp,
            server=server,
            level=level,
            message=line.strip(),
            raw=line,
        )


class ContextFoundryParser:
    """Parse Context Foundry-specific logs"""

    PHASE_PATTERN = re.compile(r'"current_phase"\s*:\s*"([^"]+)"')
    STATUS_PATTERN = re.compile(r'"status"\s*:\s*"([^"]+)"')

    def parse_phase_update(self, data: Dict, server: str) -> Optional[LogEntry]:
        """
        Parse Context Foundry phase update.

        Args:
            data: Phase update JSON
            server: Server name

        Returns:
            LogEntry with phase information
        """
        phase = data.get("current_phase", "unknown")
        status = data.get("status", "unknown")
        detail = data.get("progress_detail", "")
        iteration = data.get("test_iteration", 0)

        message = f"Phase: {phase} ({status})"
        if detail:
            message += f" - {detail}"
        if iteration > 0:
            message += f" [iteration {iteration}]"

        return LogEntry(
            timestamp=data.get("last_updated", datetime.utcnow().isoformat()),
            server=server,
            level="INFO",
            message=message,
            raw=json.dumps(data),
            structured_data=data,
        )


class LogParser:
    """
    Unified log parser.
    Delegates to specific parsers based on log source.
    """

    def __init__(self):
        self.mcp_parser = MCPLogParser()
        self.cf_parser = ContextFoundryParser()

    def parse(self, line: str, server: str) -> Optional[LogEntry]:
        """
        Parse log line.

        Args:
            line: Raw log line
            server: Server name (used to determine parser)

        Returns:
            LogEntry if parseable, None otherwise
        """
        if not line or not line.strip():
            return None

        # Try JSON parsing first (works for MCP and Context Foundry)
        try:
            data = json.loads(line)

            # Context Foundry phase update
            if "current_phase" in data:
                return self.cf_parser.parse_phase_update(data, server)

            # MCP JSON-RPC
            if "jsonrpc" in data or "method" in data or "usage" in data:
                return self.mcp_parser._parse_json_data(
                    data, line, server, datetime.utcnow().isoformat()
                )

        except json.JSONDecodeError:
            pass

        # Fallback to MCP text parser
        return self.mcp_parser.parse_line(line, server)
