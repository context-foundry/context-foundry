"""
Path Resolution Utilities

Helper functions for resolving Context Foundry installation paths.
Extracted from tools/mcp_server.py for better code organization.
"""

from pathlib import Path


def get_context_foundry_parent_dir() -> Path:
    """
    Get the parent directory of Context Foundry installation.

    This allows projects to be created as siblings of Context Foundry itself.

    Example:
        If Context Foundry is at: /Users/name/homelab/context-foundry
        This returns: /Users/name/homelab

        So new projects get created at: /Users/name/homelab/project-name

    Returns:
        Path to Context Foundry's parent directory
    """
    # __file__ is tools/mcp/path_utils.py
    # Parent of mcp/ is tools/
    # Parent of tools/ is context-foundry/
    # Parent of context-foundry/ is what we want
    cf_dir = Path(__file__).parent.parent.parent.resolve()
    return cf_dir.parent
