#!/usr/bin/env python3
"""
cf - minimal viewer for the daemon dashboard feed.

This version **does not** host its own event API. It simply:
  - Serves cf.html
  - Proxies the daemon's lightweight dashboard API:
        /events  (SSE snapshots)
        /status  (JSON snapshot)

Usage:
    python cf.py [--port 8420] [--daemon http://127.0.0.1:8420]
    open http://localhost:8420
"""

import argparse
import http.server
import socketserver
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    """Serve cf.html and proxy /events + /status to the daemon."""

    daemon_base: str = "http://127.0.0.1:8420"
    html_path: Path = Path(__file__).resolve().parent / "cf.html"

    # Endpoints to proxy (GET and POST)
    # NOTE: /auth-token is NOT proxied - it must be fetched directly from daemon (localhost only)
    PROXY_ENDPOINTS = (
        "/events",
        "/status",
        "/artifact",
        "/job-prompt",
        "/pending-approvals",
        "/approve",
        "/deny",
        "/phase-prompts",
        "/phase-inject",
        "/phase-start-review",
        "/phase-acknowledge",
        "/phase-state",
        "/transaction-stats",
        "/agent-activity",
    )

    def log_message(self, fmt, *args):
        sys.stderr.write("cf [%s] %s\n" % (self.address_string(), fmt % args))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self._serve_html()
        if parsed.path in self.PROXY_ENDPOINTS:
            # Proxy to daemon, preserving query string
            full_path = parsed.path
            if parsed.query:
                full_path += "?" + parsed.query
            return self._proxy_daemon(full_path)
        return self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path in self.PROXY_ENDPOINTS:
            return self._proxy_daemon_post(parsed.path)
        return self.send_error(404, "Not Found")

    def _serve_html(self):
        if not self.html_path.exists():
            return self.send_error(404, "cf.html not found")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with open(self.html_path, "rb") as fh:
            self.wfile.write(fh.read())

    def _proxy_daemon(self, path: str):
        url = f"{self.daemon_base}{path}"
        try:
            # Build request with optional auth header forwarding
            req = urllib.request.Request(url)
            auth_token = self.headers.get("X-CF-Auth")
            if auth_token:
                req.add_header("X-CF-Auth", auth_token)

            resp = urllib.request.urlopen(req)
            self.send_response(resp.status)

            # Check if this is an SSE endpoint
            content_type = resp.headers.get("Content-Type", "")
            is_sse = "text/event-stream" in content_type

            for key, val in resp.headers.items():
                if key.lower() in ("transfer-encoding", "content-length"):
                    continue
                self.send_header(key, val)
            self.end_headers()

            if is_sse:
                # SSE: read line by line to avoid blocking on long-lived stream
                # Use the raw socket file object for unbuffered line reads
                for line in resp:
                    self.wfile.write(line)
                    self.wfile.flush()
            else:
                # Non-SSE: chunk-based streaming is fine
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            resp.close()
        except BrokenPipeError:
            # Client disconnected - normal for SSE, ignore silently
            pass
        except ConnectionResetError:
            # Client reset connection - normal for SSE, ignore silently
            pass
        except Exception as exc:
            try:
                self.send_error(502, f"Failed to reach daemon at {url}: {exc}")
            except BrokenPipeError:
                pass  # Can't even send error, client is gone

    def _proxy_daemon_post(self, path: str):
        """Proxy POST requests to daemon."""
        url = f"{self.daemon_base}{path}"
        try:
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b""

            # Build headers, forwarding auth token if present
            headers = {
                "Content-Type": self.headers.get("Content-Type", "application/json")
            }
            auth_token = self.headers.get("X-CF-Auth")
            if auth_token:
                headers["X-CF-Auth"] = auth_token

            # Forward POST request to daemon
            req = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers=headers,
            )
            with urllib.request.urlopen(req) as resp:
                self.send_response(resp.status)
                for key, val in resp.headers.items():
                    if key.lower() in ("transfer-encoding",):
                        continue
                    self.send_header(key, val)
                self.end_headers()
                response_body = resp.read()
                self.wfile.write(response_body)
        except urllib.error.HTTPError as exc:
            self.send_response(exc.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(exc.read())
        except Exception as exc:
            try:
                self.send_error(502, f"Failed to reach daemon at {url}: {exc}")
            except BrokenPipeError:
                pass


def run_server(port: int, daemon: str, bind: str = "127.0.0.1"):
    handler = ProxyHandler
    handler.daemon_base = daemon
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer((bind, port), handler)

    print(f"cf UI: http://localhost:{port}")
    print(f"Bound to: {bind}:{port}")
    print(f"Proxying daemon feed from: {daemon}")
    if bind == "0.0.0.0":
        print(
            "NOTE: Listening on all interfaces. Auth token must be fetched directly from daemon (localhost:8420)."
        )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping cf...")
    finally:
        httpd.shutdown()
        httpd.server_close()


def main():
    parser = argparse.ArgumentParser(description="cf - view daemon dashboard feed")
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8421,
        help="Local UI port (default 8421 to avoid daemon clash)",
    )
    parser.add_argument(
        "--daemon",
        "-d",
        default="http://127.0.0.1:8420",
        help="Daemon base URL (expects /events and /status)",
    )
    parser.add_argument(
        "--bind",
        "-b",
        default="127.0.0.1",
        help="Address to bind to (default 127.0.0.1; use 0.0.0.0 for external access)",
    )
    args = parser.parse_args()
    run_server(port=args.port, daemon=args.daemon.rstrip("/"), bind=args.bind)


if __name__ == "__main__":
    main()
