"""
Relay: Feature-by-Feature Autonomous Builder

Implements Anthropic's recommended pattern for long-running agents:
- Initialization Agent: Creates feature list and project structure
- Coding Agents: Implement one feature at a time with fresh context
- Regression Testing: Random 2-feature regression before each new feature
- State via Files: feature-list.json + git commits + progress.txt

Based on: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
"""

from .orchestrator import relay_build_impl
from .feature_list import FeatureList, Feature
from .prompts import get_initialization_prompt, get_coding_agent_prompt

__all__ = [
    "relay_build_impl",
    "FeatureList",
    "Feature",
    "get_initialization_prompt",
    "get_coding_agent_prompt",
]
