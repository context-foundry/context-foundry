#!/usr/bin/env python3
"""
MCP Client for Context Foundry
Communicates with the MCP server to poll task status
"""

import json
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import time


class MCPClient:
    """
    Client for interacting with Context Foundry MCP server.

    Polls get_delegation_result() to get task status and
    reads .context-foundry/current-phase.json for detailed phase info.
    """

    def __init__(self, mcp_base_url: str = "http://localhost:8000"):
        """
        Initialize MCP client.

        Args:
            mcp_base_url: Base URL of the MCP server (for direct HTTP calls if needed)
        """
        self.mcp_base_url = mcp_base_url
        self.cache = {}  # Cache for reducing duplicate calls
        self.cache_ttl = 2  # Cache time-to-live in seconds

    def _read_phase_file(self, working_directory: str) -> Optional[Dict]:
        """
        Read .context-foundry/current-phase.json from task working directory.

        Args:
            working_directory: Path to the task's working directory

        Returns:
            Phase info dict or None if not found
        """
        try:
            phase_file = Path(working_directory) / ".context-foundry" / "current-phase.json"
            if not phase_file.exists():
                return None

            with open(phase_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading phase file: {e}")
            return None

    def _parse_mcp_response(self, response_text: str) -> Dict:
        """
        Parse MCP JSON response.

        The MCP server returns JSON strings, so we need to parse them.
        """
        try:
            # The response might be a JSON string within a JSON object
            if isinstance(response_text, str):
                return json.loads(response_text)
            return response_text
        except json.JSONDecodeError:
            return {"error": "Failed to parse MCP response", "raw": response_text}

    def get_task_status(self, task_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get status for a delegation task from MCP server.

        This simulates calling the get_delegation_result() MCP tool.
        In production, this would use the MCP protocol directly.

        Args:
            task_id: Task ID from autonomous_build_and_deploy_async()
            use_cache: Whether to use cached results (within TTL)

        Returns:
            Dict with task status including:
            - task_id
            - status (running/completed/failed/timeout)
            - elapsed_seconds
            - current_phase
            - phases_completed
            - test_iteration
            - etc.
        """
        # Check cache
        cache_key = f"task_{task_id}"
        if use_cache and cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_data

        # In a real implementation, this would call the MCP server
        # For now, we'll read from the working directory directly
        # since we have filesystem access

        # The MCP server stores active_tasks with this structure:
        # active_tasks[task_id] = {
        #     "process": process,
        #     "cmd": cmd,
        #     "cwd": working_directory,
        #     "task": task,
        #     "start_time": datetime,
        #     ...
        # }

        # We need to read from the checkpoints/status files instead
        result = self._read_from_checkpoint(task_id)

        # Cache the result
        self.cache[cache_key] = (result, time.time())

        return result

    def _read_from_checkpoint(self, task_id: str) -> Dict[str, Any]:
        """
        Read task status from checkpoint/phase files.

        This is a fallback when MCP protocol isn't available.
        It reads from the task's working directory.
        """
        # Try to find the task's working directory
        # Common patterns: /Users/name/homelab/<project>
        # or checkpoints/ralph/<session_id>

        # Check if task_id matches a checkpoint session
        checkpoint_dir = Path("checkpoints/ralph") / task_id
        if checkpoint_dir.exists():
            return self._read_checkpoint_data(checkpoint_dir)

        # Otherwise, return a basic structure
        return {
            "task_id": task_id,
            "status": "unknown",
            "error": "Task not found in checkpoints",
            "elapsed_seconds": 0
        }

    def _read_checkpoint_data(self, checkpoint_dir: Path) -> Dict[str, Any]:
        """
        Read comprehensive task data from checkpoint directory.

        Args:
            checkpoint_dir: Path to the checkpoint directory

        Returns:
            Complete task status with metrics
        """
        result = {
            "task_id": checkpoint_dir.name,
            "status": "running",
            "phases_completed": [],
            "current_phase": "Unknown"
        }

        try:
            # Read state.json
            state_file = checkpoint_dir / "state.json"
            if state_file.exists():
                with open(state_file, 'r') as f:
                    state = json.load(f)
                result.update(state)

            # Read progress.json
            progress_file = checkpoint_dir / "progress.json"
            if progress_file.exists():
                with open(progress_file, 'r') as f:
                    progress = json.load(f)
                result["progress"] = progress

            # Read current-phase.json from working directory
            if "working_directory" in result:
                phase_info = self._read_phase_file(result["working_directory"])
                if phase_info:
                    result.update(phase_info)

            # Calculate elapsed time
            if "start_time" in result:
                start = datetime.fromisoformat(result["start_time"])
                elapsed = (datetime.now() - start).total_seconds()
                result["elapsed_seconds"] = int(elapsed)

            # Check if complete
            if (checkpoint_dir / "COMPLETE").exists():
                result["status"] = "completed"

        except Exception as e:
            result["error"] = str(e)

        return result

    def list_active_tasks(self) -> List[Dict[str, Any]]:
        """
        List all active delegation tasks.

        Returns:
            List of task status dicts
        """
        tasks = []

        # Read from checkpoints directory
        checkpoints_dir = Path("checkpoints/ralph")
        if not checkpoints_dir.exists():
            return tasks

        for checkpoint_dir in checkpoints_dir.iterdir():
            if not checkpoint_dir.is_dir():
                continue

            # Skip completed sessions (for now)
            if (checkpoint_dir / "COMPLETE").exists():
                continue

            task_data = self._read_checkpoint_data(checkpoint_dir)
            tasks.append(task_data)

        return sorted(tasks, key=lambda x: x.get("start_time", ""), reverse=True)

    def get_detailed_metrics(self, task_id: str, working_directory: Optional[str] = None) -> Dict[str, Any]:
        """
        Get detailed metrics for a task.

        Reads from various .context-foundry/ files to extract comprehensive metrics.

        Args:
            task_id: Task ID
            working_directory: Optional working directory path

        Returns:
            Dict with detailed metrics including:
            - Token usage
            - Phase durations
            - Agent performance
            - Decision quality
            - Test iterations
            - Pattern effectiveness
        """
        metrics = {
            "task_id": task_id,
            "token_usage": {},
            "agent_performance": {},
            "decisions": [],
            "test_iterations": [],
            "patterns_applied": []
        }

        if not working_directory:
            # Try to get from checkpoint
            checkpoint_dir = Path("checkpoints/ralph") / task_id
            if checkpoint_dir.exists():
                state_file = checkpoint_dir / "state.json"
                if state_file.exists():
                    with open(state_file, 'r') as f:
                        state = json.load(f)
                        working_directory = state.get("working_directory")

        if not working_directory:
            return metrics

        work_dir = Path(working_directory)
        context_dir = work_dir / ".context-foundry"

        if not context_dir.exists():
            return metrics

        # Read feedback data
        feedback_dir = context_dir / "feedback"
        if feedback_dir.exists():
            for feedback_file in feedback_dir.glob("build-feedback-*.json"):
                try:
                    with open(feedback_file, 'r') as f:
                        feedback = json.load(f)
                        metrics["decisions"].extend(feedback.get("issues_found", []))
                        metrics["patterns_applied"].extend(feedback.get("successful_patterns", []))
                except Exception as e:
                    print(f"Error reading feedback file: {e}")

        # Read test iteration data
        for i in range(1, 10):  # Check up to 10 iterations
            test_file = context_dir / f"test-results-iteration-{i}.md"
            if test_file.exists():
                metrics["test_iterations"].append({
                    "iteration": i,
                    "file": str(test_file)
                })

        # Read pattern data
        patterns_dir = context_dir / "patterns"
        if patterns_dir.exists():
            common_issues_file = patterns_dir / "common-issues.json"
            if common_issues_file.exists():
                try:
                    with open(common_issues_file, 'r') as f:
                        patterns = json.load(f)
                        metrics["patterns_applied"] = patterns.get("patterns", [])
                except Exception:
                    pass

        # TODO: Extract token usage from Claude Code logs
        # This would require parsing the session logs
        metrics["token_usage"] = {
            "total": 0,  # Would need to parse from logs
            "percentage": 0.0,
            "by_phase": {}
        }

        return metrics

    def estimate_token_usage(self, task_id: str) -> Dict[str, Any]:
        """
        Estimate token usage for a task.

        This is a rough estimate based on elapsed time and phase.
        Actual token counting would require log parsing.

        Args:
            task_id: Task ID

        Returns:
            Dict with token usage estimates
        """
        status = self.get_task_status(task_id)
        elapsed = status.get("elapsed_seconds", 0)
        phase = status.get("current_phase", "Unknown")

        # Rough estimates (tokens per minute)
        phase_rates = {
            "Scout": 500,      # Research phase - moderate usage
            "Architect": 400,  # Design phase - moderate usage
            "Builder": 800,    # Implementation - high usage
            "Test": 600,       # Testing - high usage
            "Deploy": 200,     # Deployment - low usage
        }

        rate = phase_rates.get(phase, 500)
        minutes = elapsed / 60
        estimated_tokens = int(rate * minutes)

        return {
            "estimated_tokens": estimated_tokens,
            "percentage": (estimated_tokens / 200000) * 100,
            "current_phase": phase,
            "elapsed_minutes": int(minutes),
            "warning": estimated_tokens > 150000
        }


# Singleton instance
_client_instance = None


def get_client(mcp_base_url: str = "http://localhost:8000") -> MCPClient:
    """Get singleton MCP client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = MCPClient(mcp_base_url)
    return _client_instance


if __name__ == "__main__":
    # Test the client
    client = MCPClient()
    print("✅ MCP Client initialized")

    # List active tasks
    tasks = client.list_active_tasks()
    print(f"📋 Found {len(tasks)} active tasks")

    for task in tasks[:3]:  # Show first 3
        print(f"\n📌 Task: {task['task_id']}")
        print(f"   Status: {task['status']}")
        print(f"   Phase: {task.get('current_phase', 'Unknown')}")
        if "elapsed_seconds" in task:
            print(f"   Elapsed: {task['elapsed_seconds']}s")

        # Get detailed metrics
        metrics = client.get_detailed_metrics(task['task_id'])
        print(f"   Test Iterations: {len(metrics['test_iterations'])}")
        print(f"   Decisions: {len(metrics['decisions'])}")

        # Estimate tokens
        token_estimate = client.estimate_token_usage(task['task_id'])
        print(f"   Est. Tokens: {token_estimate['estimated_tokens']} ({token_estimate['percentage']:.1f}%)")
