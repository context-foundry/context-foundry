#!/usr/bin/env python3
"""
Context Foundry Banner
Displays ASCII art logo with version information
"""

import sys

# Version will be read from setup.py
VERSION = "2.0.0"


def get_banner(version: str = VERSION) -> str:
    """
    Get the Context Foundry ASCII banner with version.

    Args:
        version: Version string to display

    Returns:
        str: Formatted banner text
    """
    banner = f"""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ██████╗ ██████╗ ███╗   ██╗████████╗███████╗██╗  ██╗████████╗║
║  ██╔════╝██╔═══██╗████╗  ██║╚══██╔══╝██╔════╝╚██╗██╔╝╚══██╔══╝║
║  ██║     ██║   ██║██╔██╗ ██║   ██║   █████╗   ╚███╔╝    ██║   ║
║  ██║     ██║   ██║██║╚██╗██║   ██║   ██╔══╝   ██╔██╗    ██║   ║
║  ╚██████╗╚██████╔╝██║ ╚████║   ██║   ███████╗██╔╝ ██╗   ██║   ║
║   ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝   ╚═╝   ║
║                                                               ║
║  ███████╗ ██████╗ ██╗   ██╗███╗   ██╗██████╗ ██████╗ ██╗   ██╗║
║  ██╔════╝██╔═══██╗██║   ██║████╗  ██║██╔══██╗██╔══██╗╚██╗ ██╔╝║
║  █████╗  ██║   ██║██║   ██║██╔██╗ ██║██║  ██║██████╔╝ ╚████╔╝ ║
║  ██╔══╝  ██║   ██║██║   ██║██║╚██╗██║██║  ██║██╔══██╗  ╚██╔╝  ║
║  ██║     ╚██████╔╝╚██████╔╝██║ ╚████║██████╔╝██║  ██║   ██║   ║
║  ╚═╝      ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   ║
║                                                               ║
║           🚀 Stop Vibe Coding - Start Building 🚀             ║
║                      Version {version:<3}                     ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""
    return banner


def print_banner(version: str = VERSION, file=sys.stderr):
    """
    Print the Context Foundry banner.

    Args:
        version: Version string to display
        file: File object to print to (default: stderr for server messages)
    """
    print(get_banner(version), file=file)


if __name__ == "__main__":
    # Demo/test the banner
    print_banner()
