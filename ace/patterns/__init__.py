#!/usr/bin/env python3
"""
Pattern management system for Context Foundry.

Provides real-time pattern learning and application during builds.
"""

from .incremental_updater import IncrementalPatternUpdater

__all__ = ['IncrementalPatternUpdater']
