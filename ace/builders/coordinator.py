#!/usr/bin/env python3
"""
Parallel Builder Coordinator - Manages multiple Builder subagents running in parallel.

Each subagent writes directly to filesystem to avoid "game of telephone."
"""

import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from anthropic import Anthropic

from ..orchestrator.models import SubagentTask, SubagentResult, PhaseResult
from .builder_subagent import BuilderSubagent


class ParallelBuilderCoordinator:
    """Coordinates multiple Builder subagents running in parallel."""

    MAX_PARALLEL_BUILDERS = 4  # Limit to avoid conflicts and rate limiting

    def __init__(self, client: Optional[Anthropic] = None):
        """Initialize coordinator.

        Args:
            client: Optional Anthropic client. If None, creates new one.
        """
        if client is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            client = Anthropic(api_key=api_key)

        self.client = client

    def execute_parallel(
        self,
        tasks: List[SubagentTask],
        project_dir: Path,
        architect_result: Optional[Dict] = None
    ) -> PhaseResult:
        """
        Execute multiple Builder subagents in parallel.

        Each subagent writes directly to filesystem to avoid "game of telephone."

        Args:
            tasks: List of SubagentTask objects for builders
            project_dir: Project directory for writing files
            architect_result: Optional architect guidance

        Returns:
            PhaseResult with all builder results
        """

        print(f"\n🚀 Launching {len(tasks)} Builder subagents in parallel...")

        results = []
        total_tokens = 0

        with ThreadPoolExecutor(max_workers=min(len(tasks), self.MAX_PARALLEL_BUILDERS)) as executor:
            future_to_task = {
                executor.submit(
                    self._execute_subagent,
                    task,
                    project_dir,
                    architect_result
                ): task
                for task in tasks
            }

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                    total_tokens += result.token_usage
                except Exception as e:
                    print(f"   ❌ {task.id} failed: {e}")
                    results.append(SubagentResult(
                        task_id=task.id,
                        task_type='builder',
                        success=False,
                        error=str(e),
                        metadata={'exception_type': type(e).__name__}
                    ))

        # Check success
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        total_files = sum(len(r.files_written) for r in successful)

        print(f"✅ Builder phase complete: {len(successful)}/{len(results)} succeeded ({total_files} files)")
        if failed:
            print(f"   ⚠️  {len(failed)} builders failed")

        return PhaseResult(
            phase_name='builder',
            success=len(successful) > 0,
            subagent_results=results,
            total_tokens=total_tokens,
            error=None if len(successful) > 0 else "All builders failed"
        )

    def _execute_subagent(
        self,
        task: SubagentTask,
        project_dir: Path,
        architect_result: Optional[Dict]
    ) -> SubagentResult:
        """Execute a single Builder subagent.

        Args:
            task: SubagentTask to execute
            project_dir: Project directory
            architect_result: Architect guidance

        Returns:
            SubagentResult from execution
        """
        subagent = BuilderSubagent(self.client, task, project_dir, architect_result)
        return subagent.execute()
