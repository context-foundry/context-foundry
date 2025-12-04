#!/usr/bin/env python3
"""
Snake Game - Application Entry Point

A classic Snake game implementation using Python and pygame.
Run this file to start the game.

Usage:
    python main.py
"""

import sys

from game import Game
from constants import WINDOW_TITLE


def main() -> int:
    """
    Main entry point for the Snake game.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    print(f"Starting {WINDOW_TITLE}...")

    try:
        # Create and run game
        game = Game()
        game.run()

        print("Thanks for playing!")
        return 0

    except ImportError as e:
        print(f"Error: Missing dependency - {e}")
        print("Please install dependencies: pip install -r requirements.txt")
        return 1

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
