"""
MCP Tool Executor for Forge

Executes Context Foundry MCP tools when Claude requests them.
Bridges the gap between Claude's tool_use events and actual Python function calls.
"""

import logging
import json
from typing import Dict, Any

logger = logging.getLogger(__name__)


class MCPExecutor:
    """
    Execute Context Foundry MCP tools.

    Maps MCP tool names to Python functions and handles execution.
    """

    def __init__(self):
        """Initialize MCP executor with available tools."""
        self.tools = {}
        self._register_tools()

    def _register_tools(self):
        """Register all available Context Foundry tools."""
        try:
            # Ensure CF root is in path first
            import sys
            from pathlib import Path

            # From /tools/glass-pane/backend/services/mcp_executor.py -> /
            # Need 5 parents: services -> backend -> glass-pane -> tools -> context-foundry
            cf_root = Path(__file__).parent.parent.parent.parent.parent
            if str(cf_root) not in sys.path:
                sys.path.insert(0, str(cf_root))
                logger.info(f"Added CF root to sys.path: {cf_root}")

            # Import CF Daemon integration (the primary tool for Forge)
            from tools.mcp_utils.daemon_integration import (
                submit_autonomous_build_to_daemon,
            )

            # Map MCP tool names to functions
            # For now, only register autonomous_build_and_deploy since it's the primary
            # tool needed in Forge. Other delegation management tools can be added later
            # if needed (they would require maintaining an active_tasks dict).
            self.tools = {
                "mcp__context-foundry__autonomous_build_and_deploy": self._wrap_build_tool(
                    submit_autonomous_build_to_daemon
                ),
            }

            logger.info(f"✅ Registered {len(self.tools)} MCP tool(s) successfully")
            for tool_name in self.tools.keys():
                logger.info(f"  - {tool_name}")

        except ImportError as e:
            logger.error(f"❌ Failed to import CF tools: {e}", exc_info=True)
            self.tools = {}

    def _wrap_build_tool(self, func):
        """
        Wrap autonomous build function to match expected signature.

        The MCP tool expects parameters in a specific format, but the underlying
        function may have different parameter names.
        """

        def wrapped(**kwargs):
            # The MCP tool uses these parameter names
            task = kwargs.get("task", "")
            working_directory = kwargs.get("working_directory", "")
            mode = kwargs.get("mode", "new_project")
            github_repo_name = kwargs.get("github_repo_name")
            max_test_iterations = kwargs.get("max_test_iterations", 3)
            timeout_minutes = kwargs.get("timeout_minutes", 90.0)
            use_parallel = kwargs.get("use_parallel", False)
            incremental = kwargs.get("incremental", False)
            force_rebuild = kwargs.get("force_rebuild", False)

            # Call the underlying function
            result_json = func(
                task=task,
                working_directory=working_directory,
                github_repo_name=github_repo_name,
                mode=mode,
                max_test_iterations=max_test_iterations,
                timeout_minutes=timeout_minutes,
                use_parallel=use_parallel,
                incremental=incremental,
                force_rebuild=force_rebuild,
            )

            return result_json

        return wrapped

    def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an MCP tool.

        Args:
            tool_name: Name of the MCP tool (e.g., "mcp__context-foundry__...")
            tool_input: Tool parameters as dict

        Returns:
            Tool execution result as dict
        """
        logger.info(f"Executing MCP tool: {tool_name}")
        logger.debug(f"Tool input: {json.dumps(tool_input, indent=2)[:500]}")

        # Check if tool exists
        if tool_name not in self.tools:
            error_msg = f"Unknown tool: {tool_name}"
            logger.error(error_msg)
            return {"is_error": True, "content": [{"type": "text", "text": error_msg}]}

        try:
            # Execute the tool function
            tool_func = self.tools[tool_name]
            result = tool_func(**tool_input)

            # If result is a JSON string, parse it
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    # Result is plain text, wrap it
                    result = {"result": result}

            logger.info(f"Tool {tool_name} executed successfully")
            logger.debug(f"Tool result: {json.dumps(result, indent=2)[:500]}")

            # Format result for Claude
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            logger.error(f"{error_msg}", exc_info=True)
            return {"is_error": True, "content": [{"type": "text", "text": error_msg}]}

    def is_tool_available(self, tool_name: str) -> bool:
        """Check if a tool is available for execution."""
        return tool_name in self.tools

    def list_available_tools(self) -> list:
        """Get list of available tool names."""
        return list(self.tools.keys())
