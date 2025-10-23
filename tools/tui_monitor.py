#!/usr/bin/env python3
"""Context Foundry TUI Monitor - Entry Point"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.tui.app import ContextFoundryTUI


def main():
    """Run the TUI application"""
    try:
        app = ContextFoundryTUI()
        app.run()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
