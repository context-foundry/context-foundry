"""
Handler modules for the dashboard API.

Each module contains handler functions for a specific domain:
- base: Common utilities (CORS, auth, JSON responses)
- jobs: Job listing, details, actions (cancel, pause, resume)
- artifacts: Artifact serving and saving
- approvals: Approval gate management
- phases: Phase prompts and state
- sidekick: Sidekick chat functionality
- settings: Configuration and team settings
- status: Status and health endpoints
"""

from .base import HandlerMixin, parse_query_params
from .jobs import JobHandlersMixin
from .artifacts import ArtifactHandlersMixin
from .approvals import ApprovalHandlersMixin
from .phases import PhaseHandlersMixin
from .sidekick import SidekickHandlersMixin
from .settings import SettingsHandlersMixin
from .status import StatusHandlersMixin

__all__ = [
    "HandlerMixin",
    "parse_query_params",
    "JobHandlersMixin",
    "ArtifactHandlersMixin",
    "ApprovalHandlersMixin",
    "PhaseHandlersMixin",
    "SidekickHandlersMixin",
    "SettingsHandlersMixin",
    "StatusHandlersMixin",
]
