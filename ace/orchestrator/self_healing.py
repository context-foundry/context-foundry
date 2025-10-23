#!/usr/bin/env python3
"""
Self-Healing Loop

When validation fails:
1. Capture complete error context
2. Feed to Builder subagents
3. Retry validation
4. Repeat until success (max 3 attempts)

Based on Anthropic's error handling approach.
"""

import time
from pathlib import Path
from typing import Dict, Any, Callable, Optional

from ..validators.llm_judge import LLMJudge
from .models import SubagentTask


class SelfHealingLoop:
    """
    Self-healing mechanism that iterates until validation passes.

    Based on Anthropic's error handling:
    - Agents are stateful and errors compound
    - Use model intelligence to handle issues gracefully
    - Combine adaptability with deterministic safeguards
    """

    def __init__(self, builder_coordinator, llm_judge: Optional[LLMJudge] = None):
        """Initialize self-healing loop.

        Args:
            builder_coordinator: ParallelBuilderCoordinator instance
            llm_judge: Optional LLMJudge instance. If None, creates new one.
        """
        self.builder_coordinator = builder_coordinator
        self.llm_judge = llm_judge or LLMJudge()

    def retry_until_success(
        self,
        validation_fn: Callable,
        fix_context: Dict[str, Any],
        max_attempts: int = 3
    ) -> bool:
        """
        Run validation, and if it fails, fix and retry.

        Args:
            validation_fn: Function that returns (success, error_details)
            fix_context: Context for fixing (requirements, current state, etc.)
            max_attempts: Maximum retry attempts

        Returns:
            True if eventually successful, False otherwise
        """

        for attempt in range(1, max_attempts + 1):
            print(f"\n🔄 Validation attempt {attempt}/{max_attempts}")

            # Run validation
            success, error_details = validation_fn()

            if success:
                print(f"✅ Validation PASSED")
                return True

            print(f"❌ Validation FAILED")
            if error_details:
                print(f"   Error: {error_details.get('message', 'Unknown error')}")

            if attempt < max_attempts:
                print(f"   🔧 Analyzing failure and generating fix...")

                # Get LLM judge evaluation
                evaluation = self.llm_judge.evaluate(
                    requirements=fix_context.get('requirements', ''),
                    code_summary=fix_context.get('code_summary', {})
                )

                # Create fix tasks based on evaluation
                fix_tasks = self._create_fix_tasks(evaluation, error_details)

                if fix_tasks:
                    print(f"   🚀 Executing {len(fix_tasks)} fix tasks...")

                    # Execute fixes with dependency awareness
                    fix_result = self.builder_coordinator.execute_with_dependencies(
                        tasks=fix_tasks,
                        project_dir=fix_context.get('project_dir'),
                        architect_result=fix_context.get('architect_result')
                    )

                    if fix_result.success:
                        print(f"   ✅ Fix tasks completed")
                    else:
                        print(f"   ⚠️  Some fix tasks failed")

                    # Wait for filesystem to settle
                    time.sleep(1)
                else:
                    print(f"   ⚠️  No fix tasks could be generated")
            else:
                print(f"❌ Max attempts reached. Manual intervention required.")
                return False

        return False

    def _create_fix_tasks(
        self,
        evaluation: Dict[str, Any],
        error_details: Optional[Dict]
    ) -> list[SubagentTask]:
        """
        Create fix tasks based on evaluation and errors.

        Each critical issue becomes a focused fix task.

        Args:
            evaluation: Evaluation from LLM judge
            error_details: Error details from validation

        Returns:
            List of SubagentTask for fixes
        """

        fix_tasks = []
        task_counter = 0

        # Extract critical issues from evaluation
        for criterion in ['functionality', 'completeness', 'code_quality', 'test_coverage', 'documentation']:
            if criterion not in evaluation:
                continue

            details = evaluation[criterion]
            score = details.get('score', 1.0)

            if score < 0.7:
                # Create fix task for this issue
                issues = details.get('issues', [])
                if issues:
                    task_counter += 1
                    fix_task = SubagentTask(
                        id=f"fix_{criterion}_{task_counter}",
                        type="builder",
                        objective=f"Fix {criterion} issues: {'; '.join(issues[:3])}",  # Limit to first 3 issues
                        output_format="Fixed code files",
                        tools=["write_file", "read_file"],
                        sources=[],
                        boundaries=f"Only fix {criterion} issues, don't rewrite everything. Make minimal targeted changes.",
                        priority=0 if score < 0.5 else 1  # Higher priority for very low scores
                    )
                    fix_tasks.append(fix_task)

        # Also create task for specific runtime error if present
        if error_details and error_details.get('stderr'):
            task_counter += 1
            error_task = SubagentTask(
                id=f"fix_error_{task_counter}",
                type="builder",
                objective=f"Fix runtime error: {error_details.get('message', 'Unknown error')}",
                output_format="Fixed code",
                tools=["write_file", "read_file"],
                sources=[],
                boundaries="Fix only the error, minimal changes",
                priority=0  # Highest priority
            )
            fix_tasks.insert(0, error_task)

        # Sort by priority (lower number = higher priority)
        fix_tasks.sort(key=lambda t: t.priority)

        return fix_tasks
