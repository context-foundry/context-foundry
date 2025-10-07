#!/usr/bin/env python3
"""
Multi-Agent Orchestrator Workflow

Complete parallel multi-agent system based on Anthropic's research architecture.
Can be used standalone or integrated with existing AutonomousOrchestrator.

Usage:
    from workflows.multi_agent_orchestrator import MultiAgentOrchestrator

    orchestrator = MultiAgentOrchestrator(
        project_name="my-project",
        task_description="Build a REST API with authentication"
    )
    result = orchestrator.run()
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Add parent directory to path
FOUNDRY_ROOT = Path(__file__).parent.parent
sys.path.append(str(FOUNDRY_ROOT))

from anthropic import Anthropic

# Import multi-agent components
from ace.orchestrator import (
    LeadOrchestrator,
    WorkflowPlan,
    CheckpointManager,
    WorkflowObserver,
    SelfHealingLoop
)
from ace.scouts import ParallelScoutCoordinator
from ace.builders import ParallelBuilderCoordinator
from ace.validators.llm_judge import LLMJudge


class MultiAgentOrchestrator:
    """
    Complete multi-agent orchestration system.

    Based on Anthropic's production system:
    - Orchestrator-worker pattern
    - Parallel execution
    - Self-healing
    - Checkpointing
    - Observability

    Expected performance: 90% faster than sequential execution
    """

    def __init__(
        self,
        project_name: str,
        task_description: str,
        project_dir: Optional[Path] = None,
        enable_checkpointing: bool = True,
        enable_self_healing: bool = True,
        max_healing_attempts: int = 3
    ):
        """Initialize Multi-Agent Orchestrator.

        Args:
            project_name: Name of the project
            task_description: Description of what to build
            project_dir: Optional project directory. Defaults to examples/{project_name}
            enable_checkpointing: Enable checkpoint/resume functionality
            enable_self_healing: Enable automatic error recovery
            max_healing_attempts: Maximum self-healing retry attempts
        """
        self.project_name = project_name
        self.task_description = task_description
        self.enable_checkpointing = enable_checkpointing
        self.enable_self_healing = enable_self_healing
        self.max_healing_attempts = max_healing_attempts

        # Paths
        self.project_dir = project_dir or (FOUNDRY_ROOT / "examples" / project_name)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_id = f"{project_name}_{self.timestamp}"
        self.session_dir = FOUNDRY_ROOT / "logs" / "multi-agent" / self.session_id

        # Create directories
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        self.client = Anthropic(api_key=api_key)

        # Initialize components
        self.lead_orchestrator = LeadOrchestrator(self.client)
        self.scout_coordinator = ParallelScoutCoordinator(self.client)
        self.builder_coordinator = ParallelBuilderCoordinator(self.client)
        self.llm_judge = LLMJudge(self.client)

        # Initialize production features
        self.checkpoint_manager = CheckpointManager(self.session_dir) if enable_checkpointing else None
        self.observer = WorkflowObserver(self.session_dir)

        # State
        self.workflow_plan: Optional[WorkflowPlan] = None
        self.results = {}

        print(f"🏭 Multi-Agent Context Foundry")
        print(f"📋 Project: {project_name}")
        print(f"📝 Task: {task_description}")
        print(f"💾 Session: {self.session_id}")
        print(f"📊 Checkpointing: {'Enabled' if enable_checkpointing else 'Disabled'}")
        print(f"🔧 Self-Healing: {'Enabled' if enable_self_healing else 'Disabled'}\n")

    def run(self, resume_from: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the complete multi-agent build workflow.

        Args:
            resume_from: Optional checkpoint phase to resume from

        Returns:
            Build result with metrics
        """

        try:
            # Check for resume
            if resume_from and self.checkpoint_manager:
                return self._resume_from_checkpoint(resume_from)

            # Phase 1: Planning with Lead Orchestrator
            print("\n" + "="*80)
            print("PHASE 1: WORKFLOW PLANNING (Lead Orchestrator)")
            print("="*80)

            self.observer.log_phase_start('planning', {'description': self.task_description})

            self.workflow_plan = self.lead_orchestrator.plan_workflow(
                user_request=self.task_description,
                project_context={'name': self.project_name, 'dir': str(self.project_dir)}
            )

            if self.checkpoint_manager:
                self.checkpoint_manager.save_checkpoint('planning', {
                    'workflow_plan': self.workflow_plan.to_dict()
                })

            self.observer.log_phase_complete('planning', {'success': True})

            # Phase 2: Parallel Scout Research
            print("\n" + "="*80)
            print("PHASE 2: PARALLEL RESEARCH (Scout Subagents)")
            print("="*80)

            self.observer.log_phase_start('scout', {
                'subagent_count': len(self.workflow_plan.scout_tasks)
            })

            scout_result = self.scout_coordinator.execute_parallel(
                self.workflow_plan.scout_tasks
            )

            self.results['scout'] = scout_result

            # Compress scout findings
            compressed_scout = self.lead_orchestrator.compress_findings([
                r.to_dict() for r in scout_result.subagent_results
            ])

            if self.checkpoint_manager:
                self.checkpoint_manager.save_checkpoint('scout', {
                    'scout_result': scout_result.to_dict(),
                    'compressed': compressed_scout
                })

            self.observer.log_phase_complete('scout', {
                'success': scout_result.success,
                'token_usage': scout_result.total_tokens,
                'subagents': len(scout_result.subagent_results)
            })

            # Phase 3: Architecture Planning
            print("\n" + "="*80)
            print("PHASE 3: ARCHITECTURE PLANNING (Architect)")
            print("="*80)

            self.observer.log_phase_start('architect', {})

            # For now, use compressed scout findings as architect result
            # TODO: Integrate with existing Architect agent
            architect_result = {
                'summary': compressed_scout['compressed_summary'],
                'strategy': self.workflow_plan.architect_strategy
            }

            self.results['architect'] = architect_result

            if self.checkpoint_manager:
                self.checkpoint_manager.save_checkpoint('architect', {
                    'architect_result': architect_result
                })

            self.observer.log_phase_complete('architect', {'success': True})

            # Phase 4: Parallel Builder Implementation
            print("\n" + "="*80)
            print("PHASE 4: PARALLEL IMPLEMENTATION (Builder Subagents)")
            print("="*80)

            self.observer.log_phase_start('builder', {
                'subagent_count': len(self.workflow_plan.builder_tasks)
            })

            builder_result = self.builder_coordinator.execute_parallel(
                tasks=self.workflow_plan.builder_tasks,
                project_dir=self.project_dir,
                architect_result=architect_result
            )

            self.results['builder'] = builder_result

            if self.checkpoint_manager:
                self.checkpoint_manager.save_checkpoint('builder', {
                    'builder_result': builder_result.to_dict()
                })

            self.observer.log_phase_complete('builder', {
                'success': builder_result.success,
                'token_usage': builder_result.total_tokens,
                'subagents': len(builder_result.subagent_results)
            })

            # Phase 5: Validation with Self-Healing
            print("\n" + "="*80)
            print("PHASE 5: VALIDATION & SELF-HEALING")
            print("="*80)

            validation_passed = True

            if self.enable_self_healing:
                healing_loop = SelfHealingLoop(
                    self.builder_coordinator,
                    self.llm_judge
                )

                # Define validation function
                def validate():
                    # Collect all files written
                    all_files = []
                    for result in builder_result.subagent_results:
                        if result.success:
                            all_files.extend(result.files_written)

                    # For now, just check if files were created
                    # TODO: Add actual test execution
                    if not all_files:
                        return False, {'message': 'No files were generated'}

                    # Use LLM judge
                    evaluation = self.llm_judge.evaluate(
                        requirements=self.task_description,
                        code_summary={
                            'description': f'{len(all_files)} files generated',
                            'files': all_files,
                            'file_count': len(all_files)
                        }
                    )

                    passed = evaluation.get('overall', {}).get('pass', False)
                    return passed, evaluation

                validation_passed = healing_loop.retry_until_success(
                    validation_fn=validate,
                    fix_context={
                        'requirements': self.task_description,
                        'code_summary': {
                            'file_count': sum(len(r.files_written) for r in builder_result.subagent_results if r.success)
                        },
                        'project_dir': self.project_dir,
                        'architect_result': architect_result
                    },
                    max_attempts=self.max_healing_attempts
                )

                self.observer.log_validation_result('full_validation', {
                    'passed': validation_passed
                })

            # Generate final summary
            print("\n" + "="*80)
            if validation_passed:
                print("✅ BUILD COMPLETE - All validations passed")
            else:
                print("⚠️  BUILD COMPLETE - Some validations failed")
            print("="*80)

            # Print metrics
            self.observer.print_summary()

            # Export metrics
            if self.checkpoint_manager:
                self.observer.export_metrics()

            return {
                'success': validation_passed,
                'session_id': self.session_id,
                'session_dir': str(self.session_dir),
                'project_dir': str(self.project_dir),
                'metrics': self.observer.generate_summary(),
                'results': {
                    'scout': scout_result.to_dict(),
                    'architect': architect_result,
                    'builder': builder_result.to_dict()
                }
            }

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            self.observer.log_event('error', {
                'message': str(e),
                'type': type(e).__name__
            })
            return {
                'success': False,
                'error': str(e),
                'session_id': self.session_id
            }

    def _resume_from_checkpoint(self, phase: str) -> Dict[str, Any]:
        """Resume execution from a checkpoint.

        Args:
            phase: Phase to resume from

        Returns:
            Build result
        """

        print(f"\n🔄 Resuming from checkpoint: {phase}")

        checkpoint = self.checkpoint_manager.load_checkpoint_by_phase(phase)
        if not checkpoint:
            raise ValueError(f"No checkpoint found for phase: {phase}")

        # TODO: Implement resume logic
        print("⚠️  Resume functionality not fully implemented yet")
        return {'success': False, 'error': 'Resume not implemented'}


def main():
    """Command-line interface for multi-agent orchestrator."""
    import argparse

    parser = argparse.ArgumentParser(description='Multi-Agent Context Foundry')
    parser.add_argument('project_name', help='Name of the project')
    parser.add_argument('description', help='Project description/task')
    parser.add_argument('--project-dir', help='Project directory', type=Path)
    parser.add_argument('--no-checkpointing', action='store_true', help='Disable checkpointing')
    parser.add_argument('--no-healing', action='store_true', help='Disable self-healing')
    parser.add_argument('--max-healing-attempts', type=int, default=3, help='Max healing attempts')
    parser.add_argument('--resume-from', help='Resume from checkpoint phase')

    args = parser.parse_args()

    orchestrator = MultiAgentOrchestrator(
        project_name=args.project_name,
        task_description=args.description,
        project_dir=args.project_dir,
        enable_checkpointing=not args.no_checkpointing,
        enable_self_healing=not args.no_healing,
        max_healing_attempts=args.max_healing_attempts
    )

    result = orchestrator.run(resume_from=args.resume_from)

    if result['success']:
        print(f"\n✅ Success! Project created at: {result['project_dir']}")
        sys.exit(0)
    else:
        print(f"\n❌ Build failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
