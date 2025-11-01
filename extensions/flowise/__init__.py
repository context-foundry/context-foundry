"""
Flowise Extension for Context Foundry

A modular, private extension framework that teaches Context Foundry to become a Flowise expert.
"""

__version__ = "1.0.0"
__author__ = "Context Foundry"

# Make key modules available at package level
from . import detector
from . import analyzer
from . import extensions_loader

__all__ = ['detector', 'analyzer', 'extensions_loader']
