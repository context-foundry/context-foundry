"""
Metrics and Cost Tracking System for Context Foundry

This module provides comprehensive metrics collection, cost tracking,
and budget monitoring for autonomous builds.

Components:
- LogParser: Extract token usage from Claude API logs
- MetricsDatabase: SQLite storage for build metrics
- CostCalculator: Calculate costs with model-specific pricing
- MetricsCollector: Real-time collection orchestrator
"""

from .log_parser import LogParser, TokenUsage, APICallMetrics
from .metrics_db import MetricsDatabase, get_metrics_db
from .cost_calculator import CostCalculator, get_cost_calculator
from .collector import MetricsCollector

__all__ = [
    'LogParser',
    'TokenUsage',
    'APICallMetrics',
    'MetricsDatabase',
    'get_metrics_db',
    'CostCalculator',
    'get_cost_calculator',
    'MetricsCollector',
]

__version__ = '1.0.0'
