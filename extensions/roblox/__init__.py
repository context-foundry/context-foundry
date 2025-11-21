"""
Roblox Extension for Context Foundry

Provides Roblox game development support with Rojo workflow,
security-focused patterns, and server-authoritative architecture.
"""

from . import detector
from . import extensions_loader

__version__ = "1.0.0"
__all__ = ["detector", "extensions_loader"]
