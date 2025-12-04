"""
Tool Executor for Local Hands.

This module provides the capability to execute tools locally on behalf of a remote agent.
It implements a secure(ish) sandbox for tool execution.
"""

import subprocess
import os
import sys
from pathlib import Path
from typing import Dict, Any, Union, List, Optional
import json
import logging

logger = logging.getLogger(__name__)

class ToolExecutionError(Exception):
    """Raised when tool execution fails."""
    pass

class ToolExecutor:
    """
    Executes tools locally.
    """

    def __init__(self, working_directory: Path):
        self.working_directory = working_directory
        self.allowed_tools = {
            "run_command": self._run_command,
            "read_file": self._read_file,
            "write_file": self._write_file,
            "list_directory": self._list_directory,
        }

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool by name with arguments.
        
        Args:
            tool_name: Name of the tool to execute.
            arguments: Dictionary of arguments for the tool.
            
        Returns:
            Dictionary containing the tool output or error.
        """
        if tool_name not in self.allowed_tools:
            raise ToolExecutionError(f"Unknown tool: {tool_name}")
            
        handler = self.allowed_tools[tool_name]
        try:
            logger.info(f"Executing tool {tool_name} with args: {arguments}")
            result = handler(**arguments)
            return {
                "status": "success",
                "output": result
            }
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def _run_command(self, command: str, cwd: Optional[str] = None, timeout: int = 300) -> str:
        """
        Run a shell command.
        
        Args:
            command: The command string to execute.
            cwd: Optional working directory (relative to self.working_directory or absolute).
            timeout: Timeout in seconds.
        """
        # Resolve CWD
        if cwd:
            work_dir = Path(cwd)
            if not work_dir.is_absolute():
                work_dir = self.working_directory / cwd
        else:
            work_dir = self.working_directory
            
        if not work_dir.exists():
            raise ToolExecutionError(f"Working directory does not exist: {work_dir}")

        try:
            # Use shell=True for flexibility, but this is a security risk if exposed to untrusted input.
            # Since this is "Local Hands" for an authorized "Cloud Brain", we assume some trust.
            # But we should still be careful.
            
            # Force unbuffered output for Python
            env = dict(os.environ)
            env["PYTHONUNBUFFERED"] = "1"
            
            result = subprocess.run(
                command,
                shell=True,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            
            if result.returncode != 0:
                # Return stdout + stderr on failure to help debugging
                return f"Command failed with exit code {result.returncode}:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                
            return result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            raise ToolExecutionError(f"Command timed out after {timeout} seconds")
        except Exception as e:
            raise ToolExecutionError(f"Command execution failed: {e}")

    def _read_file(self, path: str) -> str:
        """Read a file."""
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self.working_directory / path
            
        if not file_path.exists():
            raise ToolExecutionError(f"File not found: {path}")
            
        try:
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            raise ToolExecutionError(f"Failed to read file: {e}")

    def _write_file(self, path: str, content: str) -> str:
        """Write content to a file."""
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self.working_directory / path
            
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"Successfully wrote to {path}"
        except Exception as e:
            raise ToolExecutionError(f"Failed to write file: {e}")

    def _list_directory(self, path: str = ".") -> List[str]:
        """List contents of a directory."""
        dir_path = Path(path)
        if not dir_path.is_absolute():
            dir_path = self.working_directory / path
            
        if not dir_path.exists():
            raise ToolExecutionError(f"Directory not found: {path}")
            
        if not dir_path.is_dir():
            raise ToolExecutionError(f"Not a directory: {path}")
            
        try:
            return [p.name for p in dir_path.iterdir()]
        except Exception as e:
            raise ToolExecutionError(f"Failed to list directory: {e}")
