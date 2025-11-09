#!/usr/bin/env python3
"""
Context Foundry CLI Entry Point

Usage:
    cf              # Launch Context Foundry TUI
    cf --version    # Show version
    cf --help       # Show help
"""

import sys
import argparse
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
  cf --version    Show version information
  cf --help       Show this help message

For more information, visit: https://github.com/context-foundry/context-foundry
        """,
    )

    parser.add_argument(
        "--version", action="version", version=f"Context Foundry {__version__}"
    )

    args = parser.parse_args()

    # Default action: Launch Context Foundry TUI
    launch_context_foundry()


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
