"""
Context Foundry Evolution System (CFES)

This module contains specialized agents for codebase analysis and backlog generation.
The daemon functionality has been consolidated into context_foundry.daemon.
"""

__version__ = "2.0.0"

# Scout and backlog modules remain for specialized analysis
from .agents.scout_agent import ScoutAgent
from .backlog_generator import BacklogGenerator
from .safety import enforce_sandbox_mode, is_production_directory

__all__ = [
    "ScoutAgent",
    "BacklogGenerator",
    "enforce_sandbox_mode",
    "is_production_directory",
]
