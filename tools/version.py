"""
Context Foundry Version Management

Single source of truth for version information.
All other files read from this module.
"""

from pathlib import Path

# Read version from VERSION file (single source of truth)
VERSION_FILE = Path(__file__).parent.parent / "VERSION"

def get_version() -> str:
    """
    Get the current Context Foundry version.

    Returns:
        Version string (e.g., "2.1.0")
    """
    try:
        return VERSION_FILE.read_text().strip()
    except FileNotFoundError:
        return "unknown"

def get_version_info() -> dict:
    """
    Get detailed version information.

    Returns:
        Dict with version details
    """
    version = get_version()
    parts = version.split(".")

    return {
        "version": version,
        "major": int(parts[0]) if len(parts) > 0 else 0,
        "minor": int(parts[1]) if len(parts) > 1 else 0,
        "patch": int(parts[2]) if len(parts) > 2 else 0,
        "version_string": f"v{version}",
        "display_name": f"Context Foundry v{version}"
    }

# Module-level constants for convenience
__version__ = get_version()
VERSION = __version__
VERSION_INFO = get_version_info()

if __name__ == "__main__":
    # When run directly, print version info
    info = get_version_info()
    print(f"Context Foundry {info['version_string']}")
    print(f"Major: {info['major']}")
    print(f"Minor: {info['minor']}")
    print(f"Patch: {info['patch']}")
