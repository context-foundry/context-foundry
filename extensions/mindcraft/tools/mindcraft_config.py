#!/usr/bin/env python3
"""
Mindcraft Configuration Tool

Manage Mindcraft extension configuration.
Designed for automatic discovery by Context Foundry filesystem_tools.py.

Usage:
    python mindcraft_config.py --action get
    python mindcraft_config.py --action set --key server_url --value "wss://andy.minepad.cc"
    python mindcraft_config.py --action init
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directories to path for imports
TOOL_DIR = Path(__file__).parent
EXTENSION_DIR = TOOL_DIR.parent
sys.path.insert(0, str(EXTENSION_DIR.parent.parent))
sys.path.insert(0, str(EXTENSION_DIR))

from detector import detect_mindcraft_config, get_config_file, create_default_config  # noqa: E402


def main(
    action: str = "get",
    key: str = None,
    value: str = None,
) -> str:
    """
    Manage Mindcraft configuration.

    Args:
        action: Action to perform: get, set, init
        key: Configuration key to set (for set action)
        value: Value to set (for set action)

    Returns:
        JSON string with result
    """
    result = {
        "success": False,
        "action": action,
    }

    if action == "get":
        # Get current configuration
        config = detect_mindcraft_config()
        if config:
            result["success"] = True
            result["config"] = config
            result["config_file"] = str(get_config_file())
        else:
            result["error"] = "No configuration found"
            result["hint"] = "Run with --action init to create default config"

    elif action == "init":
        # Create default configuration
        try:
            config_path = create_default_config()
            result["success"] = True
            result["config_file"] = str(config_path)
            result["message"] = "Default configuration created"

            # Load and return the config
            config = detect_mindcraft_config()
            result["config"] = config
        except Exception as e:
            result["error"] = f"Failed to create config: {e}"

    elif action == "set":
        # Set a configuration value
        if not key:
            result["error"] = "Key is required for set action"
            return json.dumps(result, indent=2)

        config_file = get_config_file()

        # Load existing config or create new
        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
        else:
            config = {}

        # Handle nested keys (e.g., "safety.avoid_blocks")
        keys = key.split(".")
        current = config
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # Parse value (try JSON first, then string)
        try:
            parsed_value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            parsed_value = value

        current[keys[-1]] = parsed_value

        # Save config
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        result["success"] = True
        result["key"] = key
        result["value"] = parsed_value
        result["config_file"] = str(config_file)

    else:
        result["error"] = f"Unknown action: {action}"

    return json.dumps(result, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Manage Mindcraft configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Get current configuration
    python mindcraft_config.py --action get

    # Initialize default configuration
    python mindcraft_config.py --action init

    # Set server URL
    python mindcraft_config.py --action set --key server_url --value "wss://andy.minepad.cc"

    # Set safety config (nested key)
    python mindcraft_config.py --action set --key safety.water_avoidance_radius --value 10

    # Set list value (JSON format)
    python mindcraft_config.py --action set --key agents --value '["andy", "dude"]'
        """,
    )

    parser.add_argument(
        "--action",
        "-a",
        choices=["get", "set", "init"],
        default="get",
        help="Action to perform",
    )
    parser.add_argument("--key", "-k", help="Configuration key (for set action)")
    parser.add_argument("--value", "-v", help="Value to set (for set action)")

    args = parser.parse_args()

    if args.action == "set" and not args.key:
        parser.error("--key is required for set action")

    result = main(
        action=args.action,
        key=args.key,
        value=args.value,
    )

    print(result)
