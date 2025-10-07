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
from anthropic import Anthropic

from ..orchestrator.models import SubagentTask, SubagentResult, PhaseResult
from .scout_subagent import ScoutSubagent


class ParallelScoutCoordinator:
    """Coordinates multiple Scout subagents running in parallel."""

    MAX_PARALLEL_SCOUTS = 5  # Limit to avoid rate limiting

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

    def execute_parallel(self, tasks: List[SubagentTask]) -> PhaseResult:
        """
        Execute multiple Scout subagents in parallel.

        Key insight from Anthropic: Parallelization cuts research time by 90%.

        Args:
            tasks: List of SubagentTask objects for scouts

        Returns:
            PhaseResult with all scout results
        """

        print(f"\n🚀 Launching {len(tasks)} Scout subagents in parallel...")

        results = []
        total_tokens = 0

        with ThreadPoolExecutor(max_workers=min(len(tasks), self.MAX_PARALLEL_SCOUTS)) as executor:
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
        subagent = ScoutSubagent(self.client, task)
        return subagent.execute()
