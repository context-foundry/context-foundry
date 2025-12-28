"""
Context Foundry Mindcraft Extension

Orchestrates Mindcraft AI agents in Minecraft for autonomous building,
gathering, and helpful assistance to human players.

Core Directive: BE HELPFUL TO HUMANS
Critical Rule: AVOID WATER AT ALL COSTS
"""

__version__ = "0.1.0"
__domain__ = "mindcraft"

from .detector import detect_mindcraft_config, is_mindcraft_available
from .client import MindcraftClient

__all__ = [
    "detect_mindcraft_config",
    "is_mindcraft_available",
    "MindcraftClient",
]
