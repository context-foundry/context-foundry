#!/usr/bin/env python3
"""
Parallel Scout Coordinator - Manages multiple Scout subagents running in parallel.

Based on Anthropic's multi-agent system:
- Executes scouts in parallel using ThreadPoolExecutor
- Collects and aggregates results
- Reports success/failure status
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from ..orchestrator.models import SubagentTask, SubagentResult, PhaseResult
from .scout_subagent import ScoutSubagent


class ParallelScoutCoordinator:
    """
    Coordinates multiple Scout subagents running in parallel.

    Dynamically scales parallelism based on research task count:
    - Few tasks (<3): 2 parallel scouts
    - Medium tasks (3-6): 4 parallel scouts
    - Many tasks (6+): 6 parallel scouts
    """

    def __init__(self, ai_client, max_parallel: Optional[int] = None):
        """Initialize coordinator.

        Args:
            ai_client: AIClient instance (provider-agnostic)
            max_parallel: Override max parallel workers (auto-scales if None)
        """
        self.ai_client = ai_client
        self.max_parallel_override = max_parallel

    def _determine_max_workers(self, task_count: int) -> int:
        """
        Determine optimal number of parallel workers based on task count.

        Args:
            task_count: Number of tasks to execute

        Returns:
            Optimal number of parallel workers
        """
        # Use override if provided
        if self.max_parallel_override is not None:
            return min(task_count, self.max_parallel_override)

        # Auto-scale based on task count
        if task_count < 3:
            # Few tasks: 2 workers
            max_workers = 2
        elif task_count < 6:
            # Medium tasks: 4 workers
            max_workers = 4
        else:
            # Many tasks: 6 workers
            max_workers = 6

        # Never exceed task count
        return min(task_count, max_workers)

    def execute_parallel(self, tasks: List[SubagentTask]) -> PhaseResult:
        """
        Execute multiple Scout subagents in parallel.

        Key insight from Anthropic: Parallelization cuts research time by 90%.
        Automatically scales parallelism based on task count.

        Args:
            tasks: List of SubagentTask objects for scouts

        Returns:
            PhaseResult with all scout results
        """
        max_workers = self._determine_max_workers(len(tasks))

        print(f"\n🚀 Launching {len(tasks)} Scout subagents (up to {max_workers} parallel)...")

        results = []
        total_tokens = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all subagent tasks
            future_to_task = {
                executor.submit(self._execute_subagent, task): task
                for task in tasks
            }

            # Collect results as they complete
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
                        task_type='scout',
                        success=False,
                        error=str(e),
                        metadata={'exception_type': type(e).__name__}
                    ))

        # Check success
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        print(f"✅ Scout phase complete: {len(successful)}/{len(results)} succeeded")
        if failed:
            print(f"   ⚠️  {len(failed)} scouts failed")

        return PhaseResult(
            phase_name='scout',
            success=len(successful) > 0,  # Success if at least one scout succeeded
            subagent_results=results,
            total_tokens=total_tokens,
            error=None if len(successful) > 0 else "All scouts failed"
        )

    def _execute_subagent(self, task: SubagentTask) -> SubagentResult:
        """Execute a single Scout subagent.

        Args:
            task: SubagentTask to execute

        Returns:
            SubagentResult from execution
        """
        subagent = ScoutSubagent(self.ai_client, task)
        return subagent.execute()
