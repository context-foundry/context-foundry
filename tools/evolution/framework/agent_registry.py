import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional, List

class AgentRegistry:
    """
    Manages the registry of available agents.
    Persists configuration to ~/.context-foundry/agents.yaml.
    """

    def __init__(self, config_path: Optional[Path] = None):
        if config_path:
            self.config_path = config_path
        else:
            self.config_path = Path.home() / ".context-foundry" / "agents.yaml"
        
        self.agents: Dict[str, Any] = {}
        self._load()

    def _load(self):
        """Load agents from the YAML configuration file."""
        if not self.config_path.exists():
            self.agents = self._get_defaults()
            self._save()
            return

        try:
            with open(self.config_path, "r") as f:
                data = yaml.safe_load(f) or {}
                self.agents = data.get("agents", {})
        except Exception as e:
            print(f"Warning: Failed to load agents registry: {e}")
            self.agents = {}

    def _save(self):
        """Save current agents to the YAML configuration file."""
        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {"agents": self.agents}
        with open(self.config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def _get_defaults(self) -> Dict[str, Any]:
        """Return default agent configurations."""
        return {
            "scout": {
                "description": "Researches codebases, answers questions, and performs analysis.",
                "provider": "local",
                "model": "claude-3-5-sonnet",
                "tools": ["search", "read_file", "list_directory"]
            },
            "architect": {
                "description": "Designs system architecture, plans changes, and creates implementation plans.",
                "provider": "local",
                "model": "claude-3-opus",
                "tools": ["search", "read_file", "list_directory", "write_file"]
            },
            "builder": {
                "description": "Writes code, implements features, and modifies files.",
                "provider": "local",
                "model": "claude-3-5-sonnet",
                "tools": ["search", "read_file", "list_directory", "write_file", "run_command"]
            },
            "test": {
                "description": "Runs tests and verifies functionality.",
                "provider": "local",
                "model": "claude-3-5-sonnet",
                "tools": ["run_command", "read_file"]
            }
        }

    def list_agents(self) -> Dict[str, Any]:
        """Return all registered agents."""
        return self.agents

    def get_agent(self, name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific agent."""
        return self.agents.get(name.lower())

    def register_agent(self, name: str, config: Dict[str, Any]):
        """Register or update an agent."""
        self.agents[name.lower()] = config
        self._save()

    def update_provider(self, name: str, provider: str, **kwargs):
        """Update the provider for a specific agent."""
        name = name.lower()
        if name not in self.agents:
            raise ValueError(f"Agent '{name}' not found.")
        
        agent = self.agents[name]
        agent["provider"] = provider
        
        # Update additional fields (e.g., agent_id)
        for key, value in kwargs.items():
            if value is not None:
                agent[key] = value
            elif key in agent:
                # Remove key if value is explicitly None
                del agent[key]
                
        self._save()

    def delete_agent(self, name: str):
        """Delete an agent from the registry."""
        if name.lower() in self.agents:
            del self.agents[name.lower()]
            self._save()
