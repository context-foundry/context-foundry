"""
Context Foundry Livestream Dashboard
Real-time monitoring with comprehensive metrics tracking

This package provides a web dashboard for monitoring Context Foundry builds
with real-time updates, token usage tracking, agent performance metrics,
decision analytics, and more.
"""

__version__ = "1.0.0"
__author__ = "Context Foundry"

# Core imports - explicitly re-exported
from .metrics_db import MetricsDatabase as MetricsDatabase, get_db as get_db
from .mcp_client import MCPClient as MCPClient, get_client as get_client

# Note: server and metrics_collector not imported by default
# to avoid starting services on package import

__all__ = [
    "MetricsDatabase",
    "get_db",
    "MCPClient",
    "get_client",
]
