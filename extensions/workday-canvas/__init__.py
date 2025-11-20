"""
Workday Canvas Kit Extension for Context Foundry

This extension enables Context Foundry to build Workday-style React applications
using the Workday Canvas Kit component library.
"""

__version__ = "1.0.0"
__author__ = "Context Foundry"

# Make key modules available at package level
from . import detector
from . import extensions_loader

__all__ = ["detector", "extensions_loader"]
