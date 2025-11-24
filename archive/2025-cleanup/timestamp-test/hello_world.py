#!/usr/bin/env python3
"""
Simple Hello World script that displays the current date and time.
"""

from datetime import datetime


def main():
    """Print Hello World message with current date and time."""
    print("Hello World!")

    # Get current date and time
    now = datetime.now()

    # Format and print the date and time
    print(f"Current Date and Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Day of Week: {now.strftime('%A')}")
    print(f"Full Format: {now.strftime('%B %d, %Y at %I:%M:%S %p')}")


if __name__ == "__main__":
    main()
