"""
MCP Server Utilities Package

This package contains modularized utilities extracted from tools/mcp_server.py
to improve code organization and maintainability.

Modules:
- output_utils: Output formatting and truncation utilities
- phase_tracking: Phase tracking file I/O
- path_utils: Path resolution helpers
- task_classification: Task intent detection
- project_detection: Project type and language detection
- pattern_management: Pattern storage and merging
"""

from tools.mcp.output_utils import truncate_output, create_output_summary
from tools.mcp.phase_tracking import read_phase_info
from tools.mcp.path_utils import get_context_foundry_parent_dir
from tools.mcp.task_classification import detect_task_intent
from tools.mcp.project_detection import detect_existing_codebase
from tools.mcp.pattern_management import (
    read_global_patterns_impl,
    save_global_patterns_impl,
    merge_project_patterns_impl,
)

__all__ = [
    # Re-exported for convenience
    "truncate_output",
    "create_output_summary",
    "read_phase_info",
    "get_context_foundry_parent_dir",
    "detect_task_intent",
    "detect_existing_codebase",
    "read_global_patterns_impl",
    "save_global_patterns_impl",
    "merge_project_patterns_impl",
]
