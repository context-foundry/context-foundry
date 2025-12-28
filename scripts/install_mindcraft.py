#!/usr/bin/env python3
"""
Mindcraft Extension Installer

Links Mindcraft tools to ~/.context-foundry/tools/ for automatic discovery.
Creates default configuration if not exists.

Usage:
    python scripts/install_mindcraft.py
    python scripts/install_mindcraft.py --uninstall
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def get_extension_dir() -> Path:
    """Get the Mindcraft extension directory."""
    script_dir = Path(__file__).parent.parent
    return script_dir / "extensions" / "mindcraft"


def get_tools_dir() -> Path:
    """Get the global Context Foundry tools directory."""
    return Path.home() / ".context-foundry" / "tools"


def get_config_dir() -> Path:
    """Get the Mindcraft config directory."""
    return Path.home() / ".context-foundry" / "mindcraft"


def install_tools() -> None:
    """Copy tool scripts to global tools directory."""
    extension_dir = get_extension_dir()
    tools_source = extension_dir / "tools"
    tools_dest = get_tools_dir()

    # Create destination directory
    tools_dest.mkdir(parents=True, exist_ok=True)

    # Copy each tool
    tool_files = [
        "mindcraft_agent.py",
        "mindcraft_status.py",
        "mindcraft_config.py",
    ]

    copied = []
    for tool_file in tool_files:
        source = tools_source / tool_file
        dest = tools_dest / tool_file

        if source.exists():
            shutil.copy2(source, dest)
            # Make executable
            os.chmod(dest, 0o755)
            copied.append(tool_file)
            print(f"  Copied: {tool_file}")
        else:
            print(f"  Warning: {tool_file} not found")

    return copied


def uninstall_tools() -> None:
    """Remove tool scripts from global tools directory."""
    tools_dest = get_tools_dir()

    tool_files = [
        "mindcraft_agent.py",
        "mindcraft_status.py",
        "mindcraft_config.py",
    ]

    removed = []
    for tool_file in tool_files:
        dest = tools_dest / tool_file
        if dest.exists():
            dest.unlink()
            removed.append(tool_file)
            print(f"  Removed: {tool_file}")

    return removed


def create_default_config() -> Path:
    """Create default configuration file."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    config_file = config_dir / "config.json"

    if not config_file.exists():
        default_config = {
            "server_url": "wss://andy.minepad.cc",
            "agents": ["andy"],
            "dry_run": False,
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

        print(f"  Created: {config_file}")
        return config_file
    else:
        print(f"  Exists: {config_file}")
        return config_file


def verify_dependencies() -> bool:
    """Check if required dependencies are installed."""
    import importlib.util

    missing = []

    if importlib.util.find_spec("socketio") is not None:
        print("  python-socketio: OK")
    else:
        missing.append("python-socketio[client]")
        print("  python-socketio: MISSING")

    if importlib.util.find_spec("aiohttp") is not None:
        print("  aiohttp: OK")
    else:
        missing.append("aiohttp")
        print("  aiohttp: MISSING")

    if missing:
        print("\n  To install missing packages:")
        print(f"    pip install {' '.join(missing)}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Install Mindcraft extension for Context Foundry"
    )
    parser.add_argument(
        "--uninstall", action="store_true", help="Remove installed tools"
    )
    parser.add_argument(
        "--skip-deps", action="store_true", help="Skip dependency check"
    )

    args = parser.parse_args()

    print("=" * 50)
    print("Mindcraft Extension Installer")
    print("=" * 50)

    if args.uninstall:
        print("\nUninstalling tools...")
        removed = uninstall_tools()
        print(f"\nRemoved {len(removed)} tools")
        return

    # Check extension exists
    extension_dir = get_extension_dir()
    if not extension_dir.exists():
        print(f"\nError: Extension not found at {extension_dir}")
        sys.exit(1)

    print(f"\nExtension: {extension_dir}")

    # Check dependencies
    if not args.skip_deps:
        print("\nChecking dependencies...")
        if not verify_dependencies():
            print("\nWarning: Some dependencies are missing")
            print("Extension will work in dry-run mode only")

    # Install tools
    print("\nInstalling tools...")
    copied = install_tools()
    print(f"Installed {len(copied)} tools to {get_tools_dir()}")

    # Create config
    print("\nSetting up configuration...")
    create_default_config()

    # Summary
    print("\n" + "=" * 50)
    print("Installation Complete!")
    print("=" * 50)
    print(f"\nTools installed to: {get_tools_dir()}")
    print(f"Config file: {get_config_dir() / 'config.json'}")
    print("\nNext steps:")
    print("  1. Edit config: ~/.context-foundry/mindcraft/config.json")
    print("  2. Set your server URL")
    print(
        "  3. Test with: python ~/.context-foundry/tools/mindcraft_status.py --dry-run"
    )
    print("\nSee extensions/mindcraft/CLAUDE.md for full documentation")


if __name__ == "__main__":
    main()
