"""
TUI Screens for CF Daemon

Screen modules for the application:
- conversation: Natural language build submission
- dashboard: Live job monitoring table
- detail: Phase pipeline and log streaming
"""

from .conversation import ConversationScreen
from .dashboard import DashboardScreen
from .detail import DetailScreen

__all__ = ["ConversationScreen", "DashboardScreen", "DetailScreen"]
