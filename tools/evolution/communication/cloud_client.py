"""
Remote Tool Executor Client.

This client allows an agent (potentially running in a different process or machine)
to execute tools on the Local Hands daemon via HTTP.
"""

import requests
import json
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class RemoteToolExecutor:
    """
    Executes tools via the Daemon HTTP API.
    """

    def __init__(self, daemon_url: str = "http://localhost:8421", working_directory: str = None, api_key: str = None):
        self.daemon_url = daemon_url.rstrip("/")
        self.working_directory = working_directory
        self.api_key = api_key

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool remotely.
        
        Args:
            tool_name: Name of the tool.
            arguments: Tool arguments.
            
        Returns:
            Tool output or error.
        """
        if not self.working_directory:
            raise ValueError("working_directory must be set before execution")

        url = f"{self.daemon_url}/tools/execute"
        payload = {
            "tool_name": tool_name,
            "arguments": arguments,
            "working_directory": str(self.working_directory)
        }
        
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            logger.debug(f"Sending remote tool execution request to {url}")
            response = requests.post(url, json=payload, headers=headers, timeout=300) # Long timeout for long-running commands
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Remote tool execution failed: {e}")
            return {
                "status": "error",
                "error": f"Network error: {str(e)}"
            }
        except json.JSONDecodeError:
            logger.error("Failed to decode response JSON")
            return {
                "status": "error",
                "error": "Invalid response from daemon"
            }
