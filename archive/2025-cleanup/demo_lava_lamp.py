#!/usr/bin/env python3
"""
Demo script for the Context Foundry lava lamp logo animation
"""

import sys
from pathlib import Path

# Add context_foundry to path
sys.path.insert(0, str(Path(__file__).parent))

from context_foundry.daemon.art import animate_lava_lamp, get_lava_lamp_art

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Context Foundry Lava Lamp Logo")
    parser.add_argument(
        "--duration", type=float, default=10.0, help="Animation duration in seconds"
    )
    parser.add_argument("--fps", type=int, default=15, help="Frames per second")
    parser.add_argument(
        "--static", action="store_true", help="Show static colored version"
    )

    args = parser.parse_args()

    if args.static:
        # Show a single frame
        print(get_lava_lamp_art(0))
    else:
        # Animate
        print("Press Ctrl+C to stop...")
        try:
            animate_lava_lamp(duration=args.duration, fps=args.fps)
        except KeyboardInterrupt:
            print("\n\nAnimation stopped.")
