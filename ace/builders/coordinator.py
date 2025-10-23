#!/usr/bin/env python3
"""
Parallel Builder Coordinator - Manages multiple Builder subagents running in parallel.

Each subagent writes directly to filesystem to avoid "game of telephone."
"""

import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict, deque

from ..orchestrator.models import SubagentTask, SubagentResult, PhaseResult
from .builder_subagent import BuilderSubagent
from .build_state_tracker import BuildStateTracker


class ParallelBuilderCoordinator:
    """
    Coordinates multiple Builder subagents running in parallel.

    Dynamically scales parallelism based on project size:
    - Small projects (<10 tasks): 2 parallel builders
    - Medium projects (10-20 tasks): 4 parallel builders
    - Large projects (20-40 tasks): 6 parallel builders
    - XLarge projects (40+ tasks): 8 parallel builders
    """

    def __init__(self, ai_client, max_parallel: Optional[int] = None):
        """Initialize coordinator.

        Args:
            ai_client: AIClient instance (provider-agnostic)
            max_parallel: Override max parallel workers (auto-scales if None)
        """
        self.ai_client = ai_client
        self.max_parallel_override = max_parallel

    def _topological_sort(self, tasks: List[SubagentTask]) -> List[List[SubagentTask]]:
        """
        Sort tasks by dependencies using topological sort.
        Returns list of levels, where each level can be executed in parallel.

        Args:
            tasks: List of tasks to sort

        Returns:
            List of task levels, where tasks in same level have no dependencies on each other
        """
        # Build dependency graph
        task_map = {task.id: task for task in tasks}
        in_degree = {task.id: len(task.dependencies) for task in tasks}
        dependents = defaultdict(list)  # Maps task_id -> list of tasks that depend on it

        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id in task_map:  # Only count dependencies that exist
                    dependents[dep_id].append(task.id)
                else:
                    # Dependency doesn't exist, reduce in-degree
                    in_degree[task.id] -= 1

        # Find tasks with no dependencies (level 0)
        levels = []
        queue = deque([task_id for task_id, degree in in_degree.items() if degree == 0])

        while queue:
            # All tasks in queue can be executed in parallel (same level)
            current_level = []

            for _ in range(len(queue)):
                task_id = queue.popleft()
                current_level.append(task_map[task_id])

                # Reduce in-degree for dependent tasks
                for dependent_id in dependents[task_id]:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        queue.append(dependent_id)

            if current_level:
                levels.append(current_level)

        # Check for cycles (tasks with dependencies not satisfied)
        remaining = [task for task in tasks if in_degree[task.id] > 0]
        if remaining:
            print(f"   ⚠️  Warning: {len(remaining)} tasks have circular dependencies, adding to final level")
            levels.append(remaining)

        return levels

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
        if task_count < 10:
            # Small project: 2 workers
            max_workers = 2
        elif task_count < 20:
            # Medium project: 4 workers
            max_workers = 4
        elif task_count < 40:
            # Large project: 6 workers
            max_workers = 6
        else:
            # XLarge project: 8 workers
            max_workers = 8

        # Never exceed task count
        return min(task_count, max_workers)

    def execute_with_dependencies(
        self,
        tasks: List[SubagentTask],
        project_dir: Path,
        architect_result: Optional[Dict] = None
    ) -> PhaseResult:
        """
        Execute tasks respecting dependency constraints.
        Tasks are grouped into levels where each level can execute in parallel.

        Args:
            tasks: List of SubagentTask objects with potential dependencies
            project_dir: Project directory for writing files
            architect_result: Optional architect guidance

        Returns:
            PhaseResult with all builder results
        """
        # Check if any tasks have dependencies
        has_dependencies = any(task.dependencies for task in tasks)

        if not has_dependencies:
            # No dependencies, use simple parallel execution
            return self.execute_parallel(tasks, project_dir, architect_result)

        # Sort tasks by dependency levels
        levels = self._topological_sort(tasks)

        print(f"\n🚀 Launching {len(tasks)} Builder subagents in {len(levels)} dependency levels...")

        all_results = []
        total_tokens = 0

        # Execute each level sequentially, but tasks within each level in parallel
        for level_num, level_tasks in enumerate(levels, 1):
            print(f"\n📍 Level {level_num}/{len(levels)}: {len(level_tasks)} tasks")

            # Determine max workers for this level
            max_workers = self._determine_max_workers(len(level_tasks))

            level_results = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_task = {
                    executor.submit(
                        self._execute_subagent,
                        task,
                        project_dir,
                        architect_result
                    ): task
                    for task in level_tasks
                }

                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        result = future.result()
                        level_results.append(result)
                        total_tokens += result.token_usage
                    except Exception as e:
                        print(f"   ❌ {task.id} failed: {e}")
                        level_results.append(SubagentResult(
                            task_id=task.id,
                            task_type='builder',
                            success=False,
                            error=str(e),
                            metadata={'exception_type': type(e).__name__}
                        ))

            # Check if all tasks in this level succeeded
            level_successes = [r for r in level_results if r.success]
            level_failures = [r for r in level_results if not r.success]

            print(f"   ✅ Level {level_num}: {len(level_successes)}/{len(level_tasks)} succeeded")

            all_results.extend(level_results)

            # If any task failed in this level, stop executing remaining levels
            if level_failures:
                print(f"   ⚠️  {len(level_failures)} tasks failed in level {level_num}, skipping remaining levels")
                break

        # Summary
        successful = [r for r in all_results if r.success]
        failed = [r for r in all_results if not r.success]
        total_files = sum(len(r.files_written) for r in successful)

        print(f"\n✅ Builder phase complete: {len(successful)}/{len(tasks)} succeeded ({total_files} files)")
        if failed:
            print(f"   ⚠️  {len(failed)} builders failed")

        return PhaseResult(
            phase_name='builder',
            success=len(successful) > 0,
            subagent_results=all_results,
            total_tokens=total_tokens,
            error=None if len(successful) > 0 else "Some or all builders failed"
        )

    def execute_incremental(
        self,
        tasks: List[SubagentTask],
        project_dir: Path,
        architect_result: Optional[Dict] = None,
        force_rebuild: bool = False
    ) -> PhaseResult:
        """
        Execute tasks incrementally - only rebuild changed files and their dependents.

        Expected impact: 70-90% faster on rebuilds, instant when no changes.

        Args:
            tasks: List of SubagentTask objects
            project_dir: Project directory
            architect_result: Optional architect guidance
            force_rebuild: If True, force full rebuild ignoring state

        Returns:
            PhaseResult with build results
        """
        # Initialize build state tracker
        state_tracker = BuildStateTracker(project_dir)

        if force_rebuild:
            print(f"\n🔨 Force rebuild requested - clearing build state")
            state_tracker.clear()
            return self.execute_with_dependencies(tasks, project_dir, architect_result)

        # Check if rebuild is needed
        needs_rebuild, reasons = state_tracker.should_rebuild()

        if not needs_rebuild:
            print(f"\n✅ No changes detected - skipping build")
            print(f"   Reasons: {', '.join(reasons)}")

            # Return cached result
            return PhaseResult(
                phase_name='builder',
                success=True,
                subagent_results=[],
                total_tokens=0,
                error=None
            )

        print(f"\n📦 Incremental build: {', '.join(reasons)}")

        # Get changed and affected files
        changed_files = state_tracker.get_changed_files()
        affected_tasks_ids = state_tracker.get_affected_tasks(changed_files)

        # Filter tasks to only affected ones
        if affected_tasks_ids:
            incremental_tasks = [t for t in tasks if t.id in affected_tasks_ids]
            print(f"   Rebuilding {len(incremental_tasks)}/{len(tasks)} affected tasks")
        else:
            # If no affected tasks found (e.g., new files), rebuild all
            incremental_tasks = tasks
            print(f"   Full rebuild ({len(tasks)} tasks)")

        # Execute affected tasks with dependency awareness
        result = self.execute_with_dependencies(incremental_tasks, project_dir, architect_result)

        # Track newly built files
        for subagent_result in result.subagent_results:
            if subagent_result.success:
                for file_path in subagent_result.files_written:
                    # Extract dependencies from architect result if available
                    dependencies = []
                    if architect_result:
                        # TODO: Extract dependencies from architecture document
                        pass

                    state_tracker.track_file(
                        file_path=file_path,
                        task_id=subagent_result.task_id,
                        dependencies=dependencies
                    )

        # Save build state
        state_tracker.save()

        # Add incremental build stats to result metadata
        result.metadata = {
            "incremental_build": True,
            "total_tasks": len(tasks),
            "rebuilt_tasks": len(incremental_tasks),
            "changed_files": len(changed_files),
            "affected_tasks": len(affected_tasks_ids)
        }

        return result

    def execute_parallel(
        self,
        tasks: List[SubagentTask],
        project_dir: Path,
        architect_result: Optional[Dict] = None
    ) -> PhaseResult:
        """
        Execute multiple Builder subagents in parallel (no dependency handling).

        Each subagent writes directly to filesystem to avoid "game of telephone."
        Automatically scales parallelism based on project size.

        Note: For dependency-aware execution, use execute_with_dependencies() instead.

        Args:
            tasks: List of SubagentTask objects for builders
            project_dir: Project directory for writing files
            architect_result: Optional architect guidance

        Returns:
            PhaseResult with all builder results
        """
        max_workers = self._determine_max_workers(len(tasks))

        print(f"\n🚀 Launching {len(tasks)} Builder subagents (up to {max_workers} parallel, no dependencies)...")

        results = []
        total_tokens = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
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
        subagent = BuilderSubagent(self.ai_client, task, project_dir, architect_result)
        return subagent.execute()
