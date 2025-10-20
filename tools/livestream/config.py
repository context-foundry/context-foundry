#!/usr/bin/env python3
"""
Configuration for Context Foundry Livestream Dashboard
"""

import os
from pathlib import Path
from typing import Dict, Any

# ============================================================================
# Server Configuration
# ============================================================================

# FastAPI server
LIVESTREAM_HOST = os.getenv("LIVESTREAM_HOST", "0.0.0.0")
LIVESTREAM_PORT = int(os.getenv("LIVESTREAM_PORT", "8080"))

# MCP Server
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")

# ============================================================================
# Polling Configuration
# ============================================================================

# How often to poll MCP server for updates (in seconds)
# Range: 3-5 seconds for balanced freshness vs overhead
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "4"))

# WebSocket update interval (in seconds)
# How often to push updates to connected clients
WEBSOCKET_UPDATE_INTERVAL = 1.0

# Cache TTL for MCP responses (in seconds)
MCP_CACHE_TTL = 2.0

# ============================================================================
# Database Configuration
# ============================================================================

# SQLite database path
DATABASE_PATH = os.getenv(
    "CF_METRICS_DB",
    str(Path.home() / ".context-foundry" / "metrics.db")
)

# Enable historical analytics
ENABLE_HISTORICAL_ANALYTICS = os.getenv("ENABLE_ANALYTICS", "true").lower() == "true"

# How long to keep metrics history (in days)
METRICS_RETENTION_DAYS = int(os.getenv("METRICS_RETENTION_DAYS", "90"))

# ============================================================================
# Paths Configuration
# ============================================================================

# Checkpoints directory (where Ralph/sessions store state)
CHECKPOINTS_DIR = Path(os.getenv("CHECKPOINTS_DIR", "checkpoints/ralph"))

# Logs directory
LOGS_DIR = Path(os.getenv("LOGS_DIR", "logs"))

# Dashboard HTML file
DASHBOARD_FILE = Path(__file__).parent / "dashboard.html"

# ============================================================================
# UI Configuration
# ============================================================================

# Always use dark mode (beautiful for overnight monitoring)
DARK_MODE = True

# Token budget limit
TOKEN_BUDGET_LIMIT = 200000

# Token warning thresholds
TOKEN_WARNING_THRESHOLD = 0.50  # 50% = yellow warning
TOKEN_CRITICAL_THRESHOLD = 0.75  # 75% = red critical

# ============================================================================
# Metrics Configuration
# ============================================================================

# Enable metrics collection
ENABLE_METRICS_COLLECTION = os.getenv("ENABLE_METRICS", "true").lower() == "true"

# Metrics to track
TRACK_TOKEN_USAGE = True
TRACK_LATENCY = True
TRACK_AGENT_PERFORMANCE = True
TRACK_DECISIONS = True
TRACK_TEST_ITERATIONS = True
TRACK_PATTERN_EFFECTIVENESS = True

# Decision quality ratings (1-5)
DECISION_QUALITY_EXCELLENT = 5
DECISION_QUALITY_GOOD = 4
DECISION_QUALITY_AVERAGE = 3
DECISION_QUALITY_POOR = 2
DECISION_QUALITY_REGRETTABLE = 1

# Decision difficulty ratings (1-5)
DECISION_DIFFICULTY_TRIVIAL = 1
DECISION_DIFFICULTY_EASY = 2
DECISION_DIFFICULTY_MODERATE = 3
DECISION_DIFFICULTY_HARD = 4
DECISION_DIFFICULTY_VERY_HARD = 5

# ============================================================================
# Agent Types
# ============================================================================

AGENT_TYPES = [
    "Scout",
    "Architect",
    "Builder",
    "Tester",
    "Deployer",
    "FeedbackAnalyzer"
]

# ============================================================================
# Phase Configuration
# ============================================================================

PHASES = [
    "Scout",
    "Architect",
    "Builder",
    "Test",
    "Screenshot",
    "Documentation",
    "Deploy",
    "Feedback"
]

# Phase colors for UI (dark mode gradients)
PHASE_COLORS = {
    "Scout": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",      # Purple
    "Architect": "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)", # Pink
    "Builder": "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",   # Blue
    "Test": "linear-gradient(135deg, #fa709a 0%, #fee140 100%)",      # Orange/Yellow
    "Screenshot": "linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)", # Cyan/Pink
    "Documentation": "linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)", # Rose
    "Deploy": "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",    # Green
    "Feedback": "linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)"   # Peach
}

# ============================================================================
# Logging Configuration
# ============================================================================

# Log level for the server
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Log file (optional - defaults to console)
LOG_FILE = os.getenv("LOG_FILE", None)

# ============================================================================
# Performance Configuration
# ============================================================================

# Maximum concurrent WebSocket connections
MAX_WEBSOCKET_CONNECTIONS = 100

# Request timeout (seconds)
REQUEST_TIMEOUT = 30

# Maximum log lines to return in API
MAX_LOG_LINES = 1000

# ============================================================================
# Feature Flags
# ============================================================================

# Enable WebSocket real-time updates
ENABLE_WEBSOCKETS = True

# Enable export functionality
ENABLE_EXPORT = True

# Enable session replay
ENABLE_SESSION_REPLAY = False  # Future feature

# Enable notifications
ENABLE_NOTIFICATIONS = False   # Future feature

# ============================================================================
# Development Configuration
# ============================================================================

# Development mode (enables hot reload, debug info, etc.)
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

# Enable CORS (for development)
ENABLE_CORS = os.getenv("ENABLE_CORS", "true").lower() == "true"

# ============================================================================
# Utility Functions
# ============================================================================

def get_checkpoint_path(session_id: str) -> Path:
    """Get path to checkpoint directory for a session."""
    return CHECKPOINTS_DIR / session_id


def get_working_directory(session_id: str) -> Path:
    """Get working directory for a session from checkpoint."""
    checkpoint_path = get_checkpoint_path(session_id)
    state_file = checkpoint_path / "state.json"

    if state_file.exists():
        import json
        with open(state_file, 'r') as f:
            state = json.load(f)
            return Path(state.get("working_directory", ""))

    return Path("")


def format_duration(seconds: int) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def format_percentage(value: float, total: float) -> str:
    """Format percentage with 1 decimal place."""
    if total == 0:
        return "0.0%"
    return f"{(value / total * 100):.1f}%"


def get_token_status(used: int, limit: int = TOKEN_BUDGET_LIMIT) -> Dict[str, Any]:
    """
    Get token usage status with warning level.

    Returns:
        Dict with percentage, level (safe/warning/critical), color
    """
    percentage = (used / limit) * 100

    if percentage < TOKEN_WARNING_THRESHOLD * 100:
        level = "safe"
        color = "green"
    elif percentage < TOKEN_CRITICAL_THRESHOLD * 100:
        level = "warning"
        color = "yellow"
    else:
        level = "critical"
        color = "red"

    return {
        "used": used,
        "limit": limit,
        "percentage": round(percentage, 1),
        "level": level,
        "color": color
    }


if __name__ == "__main__":
    # Print configuration summary
    print("📋 Context Foundry Livestream Configuration")
    print("=" * 60)
    print(f"Server: {LIVESTREAM_HOST}:{LIVESTREAM_PORT}")
    print(f"MCP Server: {MCP_SERVER_URL}")
    print(f"Poll Interval: {POLL_INTERVAL_SECONDS}s")
    print(f"Database: {DATABASE_PATH}")
    print(f"Dark Mode: {DARK_MODE}")
    print(f"Token Budget: {TOKEN_BUDGET_LIMIT:,}")
    print(f"Metrics Collection: {ENABLE_METRICS_COLLECTION}")
    print(f"Checkpoints: {CHECKPOINTS_DIR}")
    print(f"Logs: {LOGS_DIR}")
    print("=" * 60)

    # Test utility functions
    print("\nUtility Function Tests:")
    print(f"Format 125 seconds: {format_duration(125)}")
    print(f"Format 3725 seconds: {format_duration(3725)}")
    print(f"Token status (45000): {get_token_status(45000)}")
    print(f"Token status (120000): {get_token_status(120000)}")
    print(f"Token status (180000): {get_token_status(180000)}")
