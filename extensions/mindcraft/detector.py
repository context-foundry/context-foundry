"""
Mindcraft Extension Detector

Detects Mindcraft configuration and validates server connectivity.
Used by Context Foundry to determine if Mindcraft extension should be active.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any


def get_config_path() -> Path:
    """Get the path to Mindcraft configuration directory."""
    return Path.home() / ".context-foundry" / "mindcraft"


def get_config_file() -> Path:
    """Get the path to Mindcraft configuration file."""
    return get_config_path() / "config.json"


def detect_mindcraft_config() -> Optional[Dict[str, Any]]:
    """
    Detect and load Mindcraft configuration.

    Configuration precedence:
    1. Environment variables (highest)
    2. Config file (~/.context-foundry/mindcraft/config.json)
    3. Defaults (lowest)

    Returns:
        Dict with configuration if found, None otherwise
    """
    config = {}

    # Check environment variables first (highest priority)
    env_url = os.environ.get("MINDCRAFT_SERVER_URL")
    env_agents = os.environ.get("MINDCRAFT_AGENTS")
    env_dry_run = os.environ.get("MINDCRAFT_DRY_RUN", "false").lower() == "true"

    if env_url:
        config["server_url"] = env_url
    if env_agents:
        config["agents"] = [a.strip() for a in env_agents.split(",")]
    config["dry_run"] = env_dry_run

    # Check config file (medium priority)
    config_file = get_config_file()
    if config_file.exists():
        try:
            with open(config_file) as f:
                file_config = json.load(f)
            # Merge: env vars override file config
            for key, value in file_config.items():
                if key not in config:
                    config[key] = value
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load Mindcraft config: {e}")

    # Apply defaults (lowest priority)
    defaults = {
        "server_url": "ws://localhost:8080",  # Local Mindcraft default
        "agents": ["andy"],
        "dry_run": False,
        "planning": {
            "interval_seconds": 300,
            "max_concurrent_goals": 3,
        },
        "safety": {
            "avoid_blocks": ["water", "lava", "cactus"],
            "water_avoidance_radius": 5,
            "max_deaths_per_hour": 10,
        },
    }

    for key, value in defaults.items():
        if key not in config:
            config[key] = value

    return config if config.get("server_url") else None


def is_mindcraft_available() -> bool:
    """
    Check if Mindcraft extension is properly configured.

    Returns:
        True if configuration exists and appears valid
    """
    config = detect_mindcraft_config()
    if not config:
        return False

    # Must have server URL
    if not config.get("server_url"):
        return False

    # Must have at least one agent
    if not config.get("agents"):
        return False

    return True


def validate_server_url(url: str) -> bool:
    """
    Validate that a server URL looks correct.

    Args:
        url: WebSocket URL to validate

    Returns:
        True if URL appears valid
    """
    if not url:
        return False

    # Must be ws:// or wss://
    if not url.startswith(("ws://", "wss://")):
        return False

    return True


def create_default_config() -> Path:
    """
    Create a default configuration file if none exists.

    Returns:
        Path to the created config file
    """
    config_dir = get_config_path()
    config_dir.mkdir(parents=True, exist_ok=True)

    config_file = get_config_file()

    if not config_file.exists():
        default_config = {
            "server_url": "wss://andy.minepad.cc",
            "agents": ["andy"],
            "planning": {
                "interval_seconds": 300,
                "max_concurrent_goals": 3,
            },
            "safety": {
                "avoid_blocks": ["water", "lava", "cactus"],
                "water_avoidance_radius": 5,
                "protected_zones": [],
                "banned_commands": ["!clearChat"],
                "max_deaths_per_hour": 10,
            },
            "notifications": {
                "discord_webhook": None,
                "notify_on_death": True,
                "notify_on_goal_complete": False,
                "notify_on_human_join": True,
            },
        }

        with open(config_file, "w") as f:
            json.dump(default_config, f, indent=2)

    return config_file


if __name__ == "__main__":
    # Self-test
    print("Mindcraft Extension Detector")
    print("=" * 40)

    config = detect_mindcraft_config()
    if config:
        print(f"Server URL: {config.get('server_url')}")
        print(f"Agents: {config.get('agents')}")
        print(f"Dry Run: {config.get('dry_run')}")
        print(f"Available: {is_mindcraft_available()}")
    else:
        print("No configuration found")
        print("Creating default config...")
        path = create_default_config()
        print(f"Created: {path}")
