"""
Settings and configuration API handlers.

Handles config, team settings, agents, health, and status endpoints.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from .base import HandlerMixin

logger = logging.getLogger(__name__)


class SettingsHandlersMixin(HandlerMixin):
    """Mixin providing settings and config handler methods."""

    # Reference to rfile for reading request body
    rfile: any

    def handle_config(self) -> None:
        """Serve provider configuration from ~/.context-foundry/provider_config.json"""
        config_path = Path.home() / ".context-foundry" / "provider_config.json"

        config = {}
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                config = {"error": str(e)}

        self.send_json_response(config)

    def handle_agents(self) -> None:
        """Serve agent configuration from AgentRegistry."""
        try:
            from tools.llm_core.agent_registry import AgentRegistry

            registry = AgentRegistry()
            agents = registry.list_agents()
            self.send_json_response({"agents": agents})
        except Exception as e:
            logger.error(f"Failed to serve agents: {e}")
            self.send_json_error(500, str(e))

    def handle_update_agents(self) -> None:
        """Update agent configuration."""
        if not self.check_auth():
            self.send_json_error(
                401, "Unauthorized: missing or invalid X-CF-Auth header"
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8")) if body else {}

            from tools.llm_core.agent_registry import AgentRegistry

            registry = AgentRegistry()

            for agent_update in data.get("agents", []):
                agent_name = agent_update.get("name")
                if agent_name:
                    if "model" in agent_update:
                        registry.set_model(agent_name, agent_update["model"])
                    if "enabled" in agent_update:
                        registry.set_enabled(agent_name, agent_update["enabled"])
                    if "max_tokens" in agent_update:
                        registry.set_max_tokens(agent_name, agent_update["max_tokens"])

            self.send_json_response({"status": "ok"})
        except Exception as e:
            logger.error(f"Failed to update agents: {e}")
            self.send_json_error(500, str(e))

    def handle_health(self) -> None:
        """Serve health check (compatible with API /health)."""
        try:
            stats = self.server.context.store.get_job_stats()
            active_jobs = stats.get("running", 0)
            queued_jobs = stats.get("queued", 0)

            self.send_json_response(
                {
                    "status": "ok",
                    "active_jobs": active_jobs,
                    "queued_jobs": queued_jobs,
                    "timestamp": datetime.now().isoformat(),
                    "service": "dashboard",
                }
            )
        except Exception as e:
            logger.error(f"Failed to serve health: {e}")
            self.send_json_error(500, str(e))

    def handle_team_settings(self) -> None:
        """Serve team sync settings."""
        try:
            config_path = Path.home() / ".context-foundry" / "team_settings.json"
            if config_path.exists():
                settings = json.loads(config_path.read_text())
            else:
                settings = {
                    "sync_mode": "local-only",
                    "s3_bucket": "",
                    "s3_prefix": "patterns/",
                    "aws_region": "us-east-1",
                }

            self.send_json_response(settings)
        except Exception as e:
            logger.error(f"Failed to serve team settings: {e}")
            self.send_json_error(500, str(e))

    def handle_update_team_settings(self) -> None:
        """Update team settings."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            settings = json.loads(body) if body else {}

            config_path = Path.home() / ".context-foundry" / "team_settings.json"
            config_path.parent.mkdir(exist_ok=True)
            config_path.write_text(json.dumps(settings, indent=2))

            self.send_json_response({"status": "ok"})
        except Exception as e:
            logger.error(f"Failed to update team settings: {e}")
            self.send_json_error(500, str(e))

    def handle_test_s3_connection(self) -> None:
        """Test S3 connection."""
        try:
            # Mock success for now
            self.send_json_response(
                {
                    "status": "ok",
                    "message": "Connection successful (mock)",
                }
            )
        except Exception as e:
            self.send_json_error(500, str(e))

    def handle_phases(self) -> None:
        """Serve available phases from PhaseRegistry (Issue #191)."""
        try:
            from tools.mcp_utils.phase_registry import get_registry

            registry = get_registry()
            phases = []
            for phase_def in registry.list_phases():
                phases.append(
                    {
                        "id": phase_def.id,
                        "name": phase_def.name,
                        "description": phase_def.description,
                        "depends_on": phase_def.depends_on,
                        "timeout_seconds": phase_def.timeout_seconds,
                        "can_skip": phase_def.can_skip,
                        "approval_required": phase_def.approval_required,
                    }
                )

            self.send_json_response({"phases": phases})
        except Exception as e:
            logger.error(f"Failed to serve phases: {e}")
            self.send_json_error(500, str(e))

    def handle_profiles(self) -> None:
        """Serve available build profiles from PhaseRegistry (Issue #191)."""
        try:
            from tools.mcp_utils.phase_registry import get_registry

            registry = get_registry()
            profiles = []
            for profile in registry.list_profiles():
                profiles.append(
                    {
                        "name": profile.name,
                        "description": profile.description,
                        "phases": profile.phases,
                    }
                )

            self.send_json_response({"profiles": profiles})
        except Exception as e:
            logger.error(f"Failed to serve profiles: {e}")
            self.send_json_error(500, str(e))

    def handle_auth_token(self) -> None:
        """
        Serve the auth token for destructive operations.

        This endpoint allows the frontend to retrieve the auth token needed
        for POST/PUT/DELETE operations. The token is generated at server startup.
        """
        body = json.dumps({"token": self.server.context.auth_token}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.add_cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
