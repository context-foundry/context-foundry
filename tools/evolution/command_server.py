"""
Command Server - Lightweight control interface for Evolution System

Simple HTTP server for controlling daemon, triggering builds,
and querying status. Used by Mission Control UI and CLI tools.
"""

import json
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict
from urllib.parse import urlparse

from .sandboxes import SandboxManager


class CommandHandler(BaseHTTPRequestHandler):
    """Handle REST commands for Evolution System"""

    # Shared state across requests
    sandbox_manager = SandboxManager()

    def _set_headers(self, status=200, content_type="application/json"):
        """Set response headers"""
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def _json_response(self, data: Dict, status=200):
        """Send JSON response"""
        self._set_headers(status)
        self.wfile.write(json.dumps(data).encode())

    def _error_response(self, message: str, status=400):
        """Send error response"""
        self._json_response({"error": message, "success": False}, status)

    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path

        # Status endpoint
        if path == "/status":
            self._handle_status()

        # Daemon status
        elif path == "/daemon/status":
            self._handle_daemon_status()

        # MCP status
        elif path == "/mcp/status":
            self._handle_mcp_status()

        # List sandboxes
        elif path == "/sandboxes":
            self._handle_list_sandboxes()

        # GitHub issues
        elif path == "/issues":
            self._handle_list_issues()

        # Delegations
        elif path == "/delegations":
            self._handle_list_delegations()

        elif path.startswith("/delegations/"):
            task_id = path.split("/")[-1]
            self._handle_get_delegation(task_id)

        else:
            self._error_response(f"Unknown endpoint: {path}", 404)

    def do_POST(self):
        """Handle POST requests"""
        parsed = urlparse(self.path)
        path = parsed.path

        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._error_response("Invalid JSON body")
            return

        # Start build
        if path == "/build":
            self._handle_start_build(data)

        # Daemon control
        elif path == "/daemon/start":
            self._handle_daemon_start()

        elif path == "/daemon/stop":
            self._handle_daemon_stop()

        elif path == "/daemon/restart":
            self._handle_daemon_restart()

        # Sandbox cleanup
        elif path.startswith("/sandbox/") and path.endswith("/cleanup"):
            task_id = path.split("/")[2]
            self._handle_cleanup_sandbox(task_id)

        # Cancel delegation
        elif path.startswith("/delegations/") and path.endswith("/cancel"):
            task_id = path.split("/")[-2]
            self._handle_cancel_delegation(task_id)

        else:
            self._error_response(f"Unknown endpoint: {path}", 404)

    def _handle_status(self):
        """Get overall system status"""
        daemon_status = self._get_daemon_status()
        mcp_status = self._get_mcp_status()
        issue_count = self._get_issue_count()
        sandboxes = self.sandbox_manager.list_sandboxes()

        self._json_response(
            {
                "success": True,
                "daemon": daemon_status,
                "mcp": mcp_status,
                "backlog": {
                    "count": issue_count,
                    "target": 5,
                    "healthy": issue_count >= 5,
                },
                "sandboxes": {
                    "active": len(sandboxes),
                    "total_size_mb": self.sandbox_manager.get_stats()["total_size_mb"],
                },
            }
        )

    def _handle_daemon_status(self):
        """Get daemon status"""
        status = self._get_daemon_status()
        self._json_response({"success": True, **status})

    def _handle_mcp_status(self):
        """Get MCP status"""
        status = self._get_mcp_status()
        self._json_response({"success": True, **status})

    def _handle_list_sandboxes(self):
        """List active sandboxes"""
        sandboxes = self.sandbox_manager.list_sandboxes()

        # Convert Path objects to strings for JSON serialization
        sandboxes_serializable = {}
        for task_id, info in sandboxes.items():
            sandboxes_serializable[task_id] = {**info, "path": str(info["path"])}

        self._json_response(
            {
                "success": True,
                "sandboxes": sandboxes_serializable,
                "stats": self.sandbox_manager.get_stats(),
            }
        )

    def _handle_list_issues(self):
        """List GitHub issues"""
        try:
            result = subprocess.run(
                ["gh", "issue", "list", "--json", "number,title,labels,state"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                issues = json.loads(result.stdout)
                self._json_response(
                    {"success": True, "issues": issues, "count": len(issues)}
                )
            else:
                self._error_response("Failed to fetch issues")

        except Exception as e:
            self._error_response(f"Error: {e}")

    def _handle_start_build(self, data: Dict):
        """Start a new build in isolated sandbox using Claude CLI"""
        project_name = data.get("project_name")
        task = data.get("task")
        repo_url = data.get("repo_url")

        if not project_name or not task:
            self._error_response("Missing project_name or task")
            return

        sandbox_path = None
        try:
            # Generate task ID
            import uuid

            task_id = str(uuid.uuid4())

            # Create sandbox
            if not repo_url:
                repo_url = "https://github.com/context-foundry/context-foundry.git"

            sandbox_path = self.sandbox_manager.create_sandbox(repo_url, task_id)

            # Launch headless Claude instance to run the build
            # Use Claude CLI with MCP tools
            build_command = f"""
cd {sandbox_path}
claude --headless --mcp "Please use the autonomous_build_and_deploy MCP tool to build this project: {task}"
"""

            # Start build in background
            build_process = subprocess.Popen(
                ["bash", "-c", build_command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(sandbox_path),
            )

            self._json_response(
                {
                    "success": True,
                    "task_id": task_id,
                    "sandbox_path": str(sandbox_path),
                    "project_name": project_name,
                    "task": task,
                    "build_pid": build_process.pid,
                    "status": "building",
                    "message": f"Build started in headless Claude instance (PID: {build_process.pid})",
                }
            )

        except Exception as e:
            # Clean up sandbox if it was created before failure
            if sandbox_path:
                try:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.info(
                        f"🧹 Cleaning up sandbox after build start failure: {sandbox_path}"
                    )
                    self.sandbox_manager.cleanup_sandbox(sandbox_path=sandbox_path)
                    logger.info("✅ Sandbox cleanup complete")
                except Exception as cleanup_err:
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to cleanup sandbox: {cleanup_err}")

            self._error_response(f"Failed to start build: {e}")

    def _handle_daemon_start(self):
        """Start Evolution daemon"""
        try:
            cf_root = Path(__file__).parent.parent.parent
            result = subprocess.run(
                ["python3", "-m", "tools.evolution.daemon", "start"],
                capture_output=True,
                text=True,
                cwd=str(cf_root),
                timeout=5,
            )

            if result.returncode == 0:
                self._json_response({"success": True, "message": "Daemon started"})
            else:
                self._error_response(f"Failed to start daemon: {result.stderr}")

        except Exception as e:
            self._error_response(f"Error: {e}")

    def _handle_daemon_stop(self):
        """Stop Evolution daemon"""
        try:
            cf_root = Path(__file__).parent.parent.parent
            result = subprocess.run(
                ["python3", "-m", "tools.evolution.daemon", "stop"],
                capture_output=True,
                text=True,
                cwd=str(cf_root),
                timeout=5,
            )

            if result.returncode == 0:
                self._json_response({"success": True, "message": "Daemon stopped"})
            else:
                self._error_response(f"Failed to stop daemon: {result.stderr}")

        except Exception as e:
            self._error_response(f"Error: {e}")

    def _handle_daemon_restart(self):
        """Restart Evolution daemon"""
        self._handle_daemon_stop()
        self._handle_daemon_start()

    def _handle_cleanup_sandbox(self, task_id: str):
        """Cleanup a sandbox"""
        success = self.sandbox_manager.cleanup_sandbox(task_id)
        if success:
            self._json_response(
                {"success": True, "message": f"Sandbox {task_id} cleaned up"}
            )
        else:
            self._error_response(f"Sandbox {task_id} not found", 404)

    # Helper methods
    def _get_daemon_status(self) -> Dict:
        """Check daemon status"""
        try:
            cf_root = Path(__file__).parent.parent.parent
            result = subprocess.run(
                ["python3", "-m", "tools.evolution.daemon", "status"],
                capture_output=True,
                text=True,
                cwd=str(cf_root),
                timeout=2,
            )

            running = "running" in result.stdout.lower()
            pid = None

            if running:
                for line in result.stdout.split("\n"):
                    if "PID:" in line:
                        pid = int(line.split("PID:")[1].strip().rstrip(")"))
                        break

            return {
                "running": running,
                "pid": pid,
                "status": "running" if running else "stopped",
            }

        except Exception as e:
            return {"running": False, "pid": None, "status": "unknown", "error": str(e)}

    def _get_mcp_status(self) -> Dict:
        """Check MCP availability via Claude Code CLI"""
        try:
            # Check if Claude CLI is available
            result = subprocess.run(
                ["which", "claude"], capture_output=True, text=True, timeout=2
            )

            if result.returncode == 0:
                # Claude CLI is installed - MCP available via headless instances
                return {
                    "available": True,
                    "reason": "Claude CLI available - can spawn headless instances",
                }

            # Check if MCP tools are defined (even without CLI)
            mcp_server_path = Path(__file__).parent.parent / "mcp_server.py"
            if mcp_server_path.exists():
                return {
                    "available": True,
                    "reason": "MCP tools defined (use Claude CLI for builds)",
                }

            return {
                "available": False,
                "reason": "Claude CLI not found (install from https://claude.ai/cli)",
            }

        except Exception as e:
            return {"available": False, "reason": f"Error: {e}"}

    def _get_issue_count(self) -> int:
        """Get GitHub issue count"""
        try:
            result = subprocess.run(
                ["gh", "issue", "list", "--state", "open", "--json", "number"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                return len(json.loads(result.stdout))

        except Exception:
            pass

        return 0

    def _handle_list_delegations(self):
        """List all user-initiated delegations"""
        try:
            delegations_dir = Path.home() / ".context-foundry" / "delegations"
            if not delegations_dir.exists():
                self._json_response({"success": True, "delegations": [], "count": 0})
                return

            delegations = []
            for task_file in delegations_dir.glob("task-*.json"):
                try:
                    metadata = json.loads(task_file.read_text())
                    delegations.append(metadata)
                except Exception:
                    continue

            # Sort by started time (newest first)
            delegations.sort(key=lambda x: x.get("started", ""), reverse=True)

            self._json_response(
                {"success": True, "delegations": delegations, "count": len(delegations)}
            )

        except Exception as e:
            self._error_response(f"Error listing delegations: {e}")

    def _handle_get_delegation(self, task_id: str):
        """Get specific delegation by task ID"""
        try:
            delegations_dir = Path.home() / ".context-foundry" / "delegations"
            task_file = delegations_dir / f"task-{task_id}.json"

            if not task_file.exists():
                self._error_response(f"Delegation {task_id} not found", 404)
                return

            metadata = json.loads(task_file.read_text())
            self._json_response({"success": True, "delegation": metadata})

        except Exception as e:
            self._error_response(f"Error getting delegation: {e}")

    def _handle_cancel_delegation(self, task_id: str):
        """Cancel a running delegation"""
        try:
            import psutil

            delegations_dir = Path.home() / ".context-foundry" / "delegations"
            task_file = delegations_dir / f"task-{task_id}.json"

            if not task_file.exists():
                self._error_response(f"Delegation {task_id} not found", 404)
                return

            metadata = json.loads(task_file.read_text())
            pid = metadata.get("pid")

            if not pid:
                self._error_response("Delegation metadata does not contain PID")
                return

            # Kill process
            try:
                proc = psutil.Process(pid)
                proc.kill()
                proc.wait(timeout=5)

                # Update metadata
                metadata["status"] = "cancelled"
                metadata["cancelled_at"] = json.loads(
                    subprocess.run(
                        [
                            "python3",
                            "-c",
                            "from datetime import datetime; print(datetime.now().isoformat())",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    .stdout.strip()
                    .replace("'", '"')
                )

                task_file.write_text(json.dumps(metadata, indent=2))

                self._json_response(
                    {
                        "success": True,
                        "message": f"Delegation {task_id} cancelled",
                        "pid": pid,
                    }
                )

            except psutil.NoSuchProcess:
                self._json_response(
                    {
                        "success": False,
                        "error": f"Process with PID {pid} is not running",
                        "message": "Delegation may have already completed",
                    }
                )

        except Exception as e:
            self._error_response(f"Error cancelling delegation: {e}")

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass  # Silent by default


def start_server(host="127.0.0.1", port=8765):
    """
    Start command server

    Args:
        host: Host to bind to
        port: Port to listen on
    """
    server = HTTPServer((host, port), CommandHandler)
    print(f"Command server running on http://{host}:{port}")
    print("Endpoints:")
    print("  GET  /status - Overall system status")
    print("  GET  /daemon/status - Daemon status")
    print("  GET  /mcp/status - MCP status")
    print("  GET  /sandboxes - List sandboxes")
    print("  GET  /issues - List GitHub issues")
    print("  GET  /delegations - List all delegations")
    print("  GET  /delegations/{id} - Get delegation by ID")
    print("  POST /build - Start new build")
    print("  POST /daemon/start - Start daemon")
    print("  POST /daemon/stop - Stop daemon")
    print("  POST /delegations/{id}/cancel - Cancel delegation")
    print("  POST /sandbox/{id}/cleanup - Cleanup sandbox")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()


if __name__ == "__main__":
    start_server()
