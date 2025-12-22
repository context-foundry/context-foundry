"""
Base handler utilities for the dashboard API.

Contains common patterns extracted from DashboardRequestHandler:
- CORS header handling
- Authentication checking
- JSON response helpers
- Query parameter parsing
"""

import json
import logging
import secrets
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def parse_query_params(query: str) -> Dict[str, str]:
    """Parse query string into a dictionary."""
    params = {}
    if query:
        for part in query.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = v
    return params


class HandlerMixin:
    """
    Mixin class providing common handler utilities.

    Designed to be mixed into BaseHTTPRequestHandler subclasses.
    Provides CORS, auth, and JSON response helpers.
    """

    # These are provided by BaseHTTPRequestHandler
    headers: Any
    send_response: Any
    send_header: Any
    end_headers: Any
    wfile: Any
    server: Any

    def add_cors_headers(self) -> None:
        """Add CORS headers for localhost origins (dashboard UI on different ports)."""
        origin = self.headers.get("Origin", "")
        if origin and ("localhost" in origin or "127.0.0.1" in origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-CF-Auth")

    def check_auth(self) -> bool:
        """
        Check if the request has a valid auth token.

        Token must be provided in X-CF-Auth header.
        Returns True if authorized, False otherwise.
        """
        provided_token = self.headers.get("X-CF-Auth", "")
        expected_token = self.server.context.auth_token
        return secrets.compare_digest(provided_token, expected_token)

    def check_auth_with_query(self, query: str) -> bool:
        """
        Check auth from header OR query param (for EventSource which doesn't support headers).
        """
        from urllib.parse import parse_qs

        params = parse_qs(query)

        query_auth = params.get("auth", [None])[0]
        header_auth = self.headers.get("X-CF-Auth", "")
        expected_token = self.server.context.auth_token

        if header_auth and secrets.compare_digest(header_auth, expected_token):
            return True
        if query_auth and secrets.compare_digest(query_auth, expected_token):
            return True
        return False

    def send_json_response(
        self,
        data: Any,
        status_code: int = 200,
        add_cors: bool = True,
        cache_control: str = "no-cache",
    ) -> None:
        """Send a JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", cache_control)
        if add_cors:
            self.add_cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json_error(self, status_code: int, message: str) -> None:
        """Send a JSON-formatted error response for API endpoints."""
        body = json.dumps({"error": message, "status": status_code}).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.add_cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_sse_headers(self) -> None:
        """Set up headers for Server-Sent Events (SSE) response."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.add_cors_headers()
        self.end_headers()

    def send_sse_event(self, event_type: str, data: Any) -> bool:
        """
        Send an SSE event.

        Returns True if successful, False if connection was closed.
        """
        try:
            payload = json.dumps(data)
            self.wfile.write(f"event: {event_type}\n".encode())
            self.wfile.write(f"data: {payload}\n\n".encode())
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError):
            return False
        except Exception as e:
            logger.debug(f"SSE write error: {e}")
            return False


def validate_artifact_path(file_path: str) -> Optional[Path]:
    """
    Validate and normalize an artifact file path.

    Returns the resolved Path if valid, None if invalid.
    """
    if not file_path:
        return None

    # Expand user directory and resolve
    path = Path(file_path).expanduser().resolve()

    # Basic security checks
    try:
        # Ensure path doesn't escape intended directories
        # (More specific checks can be added based on allowed roots)
        if ".." in str(path):
            return None
        return path
    except Exception:
        return None
