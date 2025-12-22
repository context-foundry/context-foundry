"""
API handlers package for the CF daemon dashboard.

This package contains modular handlers extracted from the monolithic dashboard.py.
Each handler module focuses on a specific domain (jobs, artifacts, approvals, etc.).
"""

from .handlers.base import HandlerMixin, parse_query_params

__all__ = ["HandlerMixin", "parse_query_params"]
