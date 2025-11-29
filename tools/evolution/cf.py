#!/usr/bin/env python3
"""
cf.py - DEPRECATED: Use Docker instead.

The web dashboard is now served via Docker for consistency.

Usage:
    # Start the dashboard
    docker-compose up -d

    # Access at http://localhost:8421/

    # Stop
    docker-compose down

    # Rebuild after changes to cf.html
    docker-compose build && docker-compose up -d

See README.md for more details.
"""

import sys


def main():
    print("=" * 60)
    print("DEPRECATED: cf.py standalone server has been removed.")
    print()
    print("The web dashboard now runs via Docker for consistency.")
    print()
    print("Usage:")
    print("  docker-compose up -d        # Start dashboard")
    print("  docker-compose down         # Stop dashboard")
    print()
    print("Access at: http://localhost:8421/")
    print("=" * 60)
    sys.exit(1)


if __name__ == "__main__":
    main()
