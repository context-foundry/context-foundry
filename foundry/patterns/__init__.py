"""
Pattern Library
Self-improving system that learns from successful builds.
"""

from .pattern_manager import PatternLibrary
from .pattern_extractor import PatternExtractor
from .failure_pattern_extractor import FailurePatternExtractor

__all__ = ['PatternLibrary', 'PatternExtractor', 'FailurePatternExtractor']
