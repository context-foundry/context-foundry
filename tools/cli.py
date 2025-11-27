#!/usr/bin/env python3
"""
Context Foundry CLI Entry Point

Usage:
    cf              # Launch Context Foundry TUI
    cf setup        # Configure Claude Code MCP integration
    cf --version    # Show version
    cf --help       # Show help
"""

import sys
import argparse
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from __version__ import __version__


def main():
    """Main CLI entry point"""
    # Check Python version at runtime
    if sys.version_info < (3, 10):
        print(
            f"""
❌ Error: Python 3.10 or higher required

Your current Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}
Context Foundry requires: Python 3.10+

Why? Context Foundry uses Python 3.10+ exclusive features:
  • Structural pattern matching (match statements)
  • Advanced type hints (TypeAlias, ParamSpec, etc.)

Solutions:
  1. Upgrade Python: brew install python@3.11 (macOS)
  2. Use pyenv: pyenv install 3.11 && pyenv local 3.11
  3. Use a virtual environment with Python 3.10+:
     python3.11 -m venv venv
     source venv/bin/activate
     cf

For more help: https://github.com/context-foundry/context-foundry/blob/main/INSTALL.md
""",
            file=sys.stderr,
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(
        prog="cf",
        description="Context Foundry - The AI That Builds Itself",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cf              Launch Context Foundry TUI
  cf setup        Configure Claude Code MCP integration
  cf --version    Show version information
  cf --help       Show this help message

For more information, visit: https://github.com/context-foundry/context-foundry
        """,
    )

    parser.add_argument(
        "--version", action="version", version=f"Context Foundry {__version__}"
    )

    parser.add_argument(
        "command",
        nargs="?",
        choices=["setup"],
        help="Command to run (default: launch TUI)",
    )

    args = parser.parse_args()

    if args.command == "setup":
        setup_claude_code()
    else:
        # Default action: Launch Context Foundry TUI
        launch_context_foundry()


def setup_claude_code():
    """Configure Claude Code MCP integration automatically"""
    print("🔧 Setting up Context Foundry for Claude Code...\n")

    # Find the MCP server path
    mcp_server_path = Path(__file__).parent / "mcp_server.py"
    if not mcp_server_path.exists():
        print(f"❌ Error: MCP server not found at {mcp_server_path}", file=sys.stderr)
        sys.exit(1)

    mcp_server_path = mcp_server_path.resolve()

    # Claude Code settings file
    claude_settings_path = Path.home() / ".claude" / "mcp_settings.json"

    # Load existing settings or create new
    if claude_settings_path.exists():
        try:
            with open(claude_settings_path) as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            print(
                f"⚠️  Warning: Invalid JSON in {claude_settings_path}, creating backup..."
            )
            backup_path = claude_settings_path.with_suffix(".json.backup")
            claude_settings_path.rename(backup_path)
            settings = {}
    else:
        settings = {}

    # Ensure mcpServers key exists
    if "mcpServers" not in settings:
        settings["mcpServers"] = {}

    # Add or update context-foundry config
    settings["mcpServers"]["context-foundry"] = {
        "command": "python",
        "args": [str(mcp_server_path)],
    }

    # Create directory if needed
    claude_settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Write settings
    with open(claude_settings_path, "w") as f:
        json.dump(settings, f, indent=2)

    print("✅ Claude Code configured successfully!\n")
    print(f"   Settings file: {claude_settings_path}")
    print(f"   MCP server:    {mcp_server_path}\n")
    print("🚀 You can now use Context Foundry in Claude Code!")
    print('   Just ask: "Use CF to build a todo app"\n')


def launch_context_foundry():
    """Launch the Context Foundry TUI"""
    try:
        # Import and run Context Foundry TUI
        from tools.evolution.mission_control import MissionControlApp

        app = MissionControlApp()
        app.run()

    except ImportError as e:
        print(
            f"""
❌ Error: Missing dependencies

Context Foundry requires additional Python packages to run.

Please install them:
    cd {Path(__file__).parent.parent}
    pip install -r requirements-mcp.txt

Error details: {e}
""",
            file=sys.stderr,
        )
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nGoodbye! 👋")
        sys.exit(0)

    except Exception as e:
        print(
            f"""
❌ Error launching Context Foundry

{str(e)}

Please report this issue at:
https://github.com/context-foundry/context-foundry/issues
""",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
