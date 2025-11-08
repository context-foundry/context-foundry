"""Evolution Modes - Plugin system for CFES"""

from .base_mode import BaseEvolutionMode, TaskResult
from .self_improvement import SelfImprovementMode
from .chaos_creative import ChaosCreativeMode
from .research_discovery import ResearchDiscoveryMode

__all__ = [
    "BaseEvolutionMode",
    "TaskResult",
    "SelfImprovementMode",
    "ChaosCreativeMode",
    "ResearchDiscoveryMode",
]
