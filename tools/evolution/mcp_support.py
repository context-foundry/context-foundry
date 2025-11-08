"""Helpers for detecting MCP capability without crashing the daemon."""

from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from typing import Dict, Tuple


def _detect_mcp_capabilities() -> Tuple[bool, str]:
    """Return (available, reason) without importing heavy MCP modules."""
    if sys.version_info < (3, 10):
        return False, "Python 3.10+ required for MCP features"

    fastmcp_spec = importlib.util.find_spec("fastmcp")
    if fastmcp_spec is None:
        return False, "fastmcp package not installed (pip install -r requirements-mcp.txt)"

    return True, ""


@lru_cache(maxsize=1)
def _cached_capabilities() -> Tuple[bool, str]:
    """Cache detection so repeated checks stay cheap."""
    return _detect_mcp_capabilities()


def get_mcp_capabilities(force_refresh: bool = False) -> Dict[str, str]:
    """
    Inspect MCP dependency availability.

    Args:
        force_refresh: When True, bypass the cache and re-detect.

    Returns:
        Dict with shape {"available": bool, "reason": str}
    """
    if force_refresh:
        _cached_capabilities.cache_clear()  # type: ignore[attr-defined]

    available, reason = _cached_capabilities()
    return {"available": available, "reason": reason}
