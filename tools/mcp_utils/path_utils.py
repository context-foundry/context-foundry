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
        If Context Foundry is at: {CF_ROOT}
        This returns: ~/projects

        So new projects get created at: ~/projects/project-name

    Returns:
        Path to Context Foundry's parent directory
    """
    # __file__ is tools/mcp/path_utils.py
    # Parent of mcp/ is tools/
    # Parent of tools/ is context-foundry/
    # Parent of context-foundry/ is what we want
    cf_dir = Path(__file__).parent.parent.parent.resolve()
    return cf_dir.parent


def get_projects_root() -> Path:
    """
    Get the root directory where new projects should be created.

    By default, projects are created as siblings to the Context Foundry
    installation directory. This keeps all projects organized in one place
    and avoids polluting system directories like /tmp.

    Example:
        If Context Foundry is installed at: {CF_ROOT}
        New projects will be created at: ~/projects/project-name

    Pattern:
        context-foundry/          (this repo)
        project-1/                (created project)
        project-2/                (created project)
        weather-app/              (created project)

    Returns:
        Path to the root directory for new projects (same as Context Foundry parent)

    See Also:
        get_context_foundry_parent_dir() - Alias for backward compatibility
    """
    return get_context_foundry_parent_dir()
