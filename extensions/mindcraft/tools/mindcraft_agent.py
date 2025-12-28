#!/usr/bin/env python3
"""
Mindcraft Agent Control Tool

Direct control of Mindcraft agents: send messages, start/stop, restart.
Designed for automatic discovery by Context Foundry filesystem_tools.py.

Usage:
    python mindcraft_agent.py --agent andy --command "Hello!"
    python mindcraft_agent.py --agent andy --action start
    python mindcraft_agent.py --agent andy --action stop
    python mindcraft_agent.py --agent andy --action restart
    python mindcraft_agent.py --agent andy --action status
    python mindcraft_agent.py --dry-run --agent andy --command "Test"
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
from detector import detect_mindcraft_config  # noqa: E402


def main(
    agent: str,
    command: str = None,
    action: str = None,
    dry_run: bool = False,
    server_url: str = None,
) -> str:
    """
    Control a Mindcraft agent.

    Args:
        agent: Agent name (e.g., "andy")
        command: Message to send to agent (optional)
        action: Action to perform: start, stop, restart, status (optional)
        dry_run: If True, simulate without real connection
        server_url: Override server URL

    Returns:
        JSON string with result
    """
    # Load config
    config = detect_mindcraft_config()
    if server_url:
        config["server_url"] = server_url
    if dry_run:
        config["dry_run"] = True

    # Create client
    client = MindcraftClientSync(
        server_url=config.get("server_url", "ws://localhost:8080"),
        dry_run=config.get("dry_run", False),
    )

    result = {
        "success": False,
        "agent": agent,
        "action": action or "message",
        "dry_run": client.dry_run,
    }

    # Connect
    if not client.connect():
        result["error"] = "Failed to connect to MindServer"
        return json.dumps(result, indent=2)

    try:
        # Handle actions
        if action == "status":
            status = client.get_agent_status(agent)
            if status:
                result["success"] = True
                result["status"] = status.to_dict()
            else:
                result["error"] = f"Agent '{agent}' not found"

        elif action == "start":
            success = client.start_agent(agent)
            result["success"] = success
            if not success:
                result["error"] = "Failed to start agent"

        elif action == "stop":
            success = client.stop_agent(agent)
            result["success"] = success
            if not success:
                result["error"] = "Failed to stop agent"

        elif action == "restart":
            success = client.restart_agent(agent)
            result["success"] = success
            if not success:
                result["error"] = "Failed to restart agent"

        elif command:
            # Send message/command
            success = client.send_message(agent, command)
            result["success"] = success
            result["command"] = command
            if not success:
                result["error"] = "Failed to send message"

        else:
            result["error"] = "No action or command specified"

    finally:
        client.disconnect()

    return json.dumps(result, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Control Mindcraft agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Send a message to Andy
    python mindcraft_agent.py --agent andy --command "Hello!"

    # Check Andy's status
    python mindcraft_agent.py --agent andy --action status

    # Restart Andy
    python mindcraft_agent.py --agent andy --action restart

    # Dry run test
    python mindcraft_agent.py --dry-run --agent andy --command "Test"
        """,
    )

    parser.add_argument("--agent", "-a", required=True, help="Agent name (e.g., andy)")
    parser.add_argument("--command", "-c", help="Message/command to send to agent")
    parser.add_argument(
        "--action",
        choices=["start", "stop", "restart", "status"],
        help="Action to perform",
    )
    parser.add_argument("--server-url", "-s", help="Override server URL")
    parser.add_argument(
        "--dry-run", "-d", action="store_true", help="Simulate without real connection"
    )

    args = parser.parse_args()

    if not args.action and not args.command:
        parser.error("Either --action or --command is required")

    result = main(
        agent=args.agent,
        command=args.command,
        action=args.action,
        dry_run=args.dry_run,
        server_url=args.server_url,
    )

    print(result)
