"""Context Foundry version information.

This file is the single source of truth for version numbering.
All other files should import from here to maintain consistency.

Usage:
    from __version__ import __version__, __release_date__
    print(f"Context Foundry {__version__}")
"""

__version__ = "2.1.0"
__release_date__ = "2025-10-24"
__version_info__ = tuple(int(i) for i in __version__.split("."))

# Semantic versioning components
MAJOR = __version_info__[0]
MINOR = __version_info__[1]
PATCH = __version_info__[2]
