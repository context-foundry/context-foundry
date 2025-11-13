"""
Task Classification Utilities

Functions for detecting user intent from task descriptions.
Extracted from tools/mcp_server.py for better code organization.
"""


def detect_task_intent(task: str) -> str:
    """
    Detect the user's intent from the task description.

    Args:
        task: The task description string

    Returns:
        Mode string: "new_project", "fix_bug", "add_feature", "upgrade_deps", "refactor", or "add_tests"
    """
    task_lower = task.lower()

    # Fix/bug keywords
    if any(
        word in task_lower
        for word in ["fix", "bug", "issue", "error", "broken", "repair"]
    ):
        return "fix_bug"

    # Upgrade/dependency keywords
    if any(
        word in task_lower
        for word in [
            "upgrade",
            "update dependencies",
            "update deps",
            "update packages",
            "update all",
            "migrate to",
        ]
    ):
        return "upgrade_deps"

    # Refactor keywords
    if any(
        word in task_lower
        for word in ["refactor", "restructure", "reorganize", "clean up"]
    ):
        return "refactor"

    # Test keywords
    if any(
        word in task_lower
        for word in ["add tests", "write tests", "test coverage", "unit test"]
    ):
        return "add_tests"

    # Add feature/enhance keywords
    if any(
        word in task_lower
        for word in [
            "add",
            "enhance",
            "improve",
            "implement",
            "create feature",
            "new feature",
        ]
    ):
        return "add_feature"

    # Default to new project if no enhancement keywords found
    return "new_project"
