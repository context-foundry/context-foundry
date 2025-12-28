#!/usr/bin/env python3
"""
Mindcraft Status Tool

Get status of all agents and server connection.
Designed for automatic discovery by Context Foundry filesystem_tools.py.

Usage:
    python mindcraft_status.py
    python mindcraft_status.py --agent andy
    python mindcraft_status.py --dry-run
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

from client import MindcraftClientSync  # noqa: E402
from detector import detect_mindcraft_config, is_mindcraft_available  # noqa: E402


def main(
    agent: str = None,
    dry_run: bool = False,
    server_url: str = None,
) -> str:
    """
    Get Mindcraft status.

    Args:
        agent: Specific agent name (optional, shows all if not specified)
        dry_run: If True, simulate without real connection
        server_url: Override server URL

    Returns:
        JSON string with status information
    """
    # Load config
    config = detect_mindcraft_config()
    if server_url:
        config["server_url"] = server_url
    if dry_run:
        config["dry_run"] = True

    result = {
        "success": False,
        "dry_run": config.get("dry_run", False),
        "config_available": is_mindcraft_available(),
        "server_url": config.get("server_url"),
    }

    # Create client
    client = MindcraftClientSync(
        server_url=config.get("server_url", "ws://localhost:8080"),
        dry_run=config.get("dry_run", False),
    )

    # Connect
    if not client.connect():
        result["error"] = "Failed to connect to MindServer"
        result["connected"] = False
        return json.dumps(result, indent=2)

    result["connected"] = True

    try:
        if agent:
            # Get specific agent
            status = client.get_agent_status(agent)
            if status:
                result["success"] = True
                result["agent"] = status.to_dict()
            else:
                result["error"] = f"Agent '{agent}' not found"
                result["success"] = False
        else:
            # Get all agents
            agents = client.get_all_agents()
            result["success"] = True
            result["agents"] = {name: state.to_dict() for name, state in agents.items()}
            result["agent_count"] = len(agents)

    finally:
        client.disconnect()

    return json.dumps(result, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Get Mindcraft status",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Get all agents status
    python mindcraft_status.py

    # Get specific agent status
    python mindcraft_status.py --agent andy

    # Dry run test
    python mindcraft_status.py --dry-run
        """,
    )

    parser.add_argument("--agent", "-a", help="Specific agent name (optional)")
    parser.add_argument("--server-url", "-s", help="Override server URL")
    parser.add_argument(
        "--dry-run", "-d", action="store_true", help="Simulate without real connection"
    )

    args = parser.parse_args()

    result = main(
        agent=args.agent,
        dry_run=args.dry_run,
        server_url=args.server_url,
    )

    print(result)
