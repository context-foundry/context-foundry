#!/usr/bin/env python3
"""
Mindcraft Orchestrator Tool

Starts the full autonomous system.
Designed for automatic discovery by Context Foundry.

Usage:
    python mindcraft_orchestrate.py --dry-run
    python mindcraft_orchestrate.py --server wss://andy.minepad.cc
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directories to path for imports
TOOL_DIR = Path(__file__).parent
EXTENSION_DIR = TOOL_DIR.parent
sys.path.insert(0, str(EXTENSION_DIR.parent.parent))
sys.path.insert(0, str(EXTENSION_DIR))

from orchestrator import run_orchestrator  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Run Mindcraft Orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Run in simulation mode")
    parser.add_argument("--server", help="MindServer URL")

    args = parser.parse_args()

    try:
        asyncio.run(run_orchestrator(dry_run=args.dry_run, server_url=args.server))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
