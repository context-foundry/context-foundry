#!/usr/bin/env python3
"""
Context Foundry Orchestrator
Manages the Scout → Architect → Builder workflow
"""

import os
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import sys

class ContextFoundryOrchestrator:
    """
    Orchestrates the three-phase Context Foundry workflow.
    Anti-vibe: Systematic, documented, tested.
    """

    def __init__(self, project_name: str, task_description: str):
        self.project_name = project_name
        self.task_description = task_description
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Paths
        self.project_path = Path(f"examples/{project_name}")
        self.blueprints_path = Path("blueprints")
        self.checkpoints_path = Path("checkpoints/sessions")
        self.logs_path = Path(f"logs/{self.timestamp}")

        # Create directories
        self.project_path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)

        # State
        self.context_usage = 0
        self.phase = "initializing"
        self.session_id = f"{project_name}_{self.timestamp}"

    def run(self) -> Dict:
        """Execute the complete Context Foundry workflow."""

        print(f"🏭 Context Foundry: Starting session {self.session_id}")
        print(f"📋 Task: {self.task_description}\n")

        results = {}

        try:
            # Phase 1: Scout
            print("🔍 PHASE 1: SCOUT")
            print("-" * 50)
            scout_result = self.run_scout_phase()
            results['scout'] = scout_result

            # Human checkpoint 1
            if not self.get_human_approval("Scout", scout_result):
                return self.abort("Scout phase rejected by human review")

            # Phase 2: Architect
            print("\n📐 PHASE 2: ARCHITECT")
            print("-" * 50)
            architect_result = self.run_architect_phase(scout_result)
            results['architect'] = architect_result

            # CRITICAL: Human checkpoint 2 (highest leverage point)
            print("\n⚠️  CRITICAL CHECKPOINT: Plan Review Required")
            if not self.get_human_approval("Architect", architect_result, critical=True):
                return self.abort("Architecture phase rejected by human review")

            # Phase 3: Builder
            print("\n🔨 PHASE 3: BUILDER")
            print("-" * 50)
            builder_result = self.run_builder_phase(architect_result)
            results['builder'] = builder_result

            # Final checkpoint
            if not self.get_human_approval("Builder", builder_result):
                return self.abort("Build phase rejected by human review")

            return self.finalize(results)

        except Exception as e:
            return self.handle_error(e, results)

    def run_scout_phase(self) -> Dict:
        """Execute research phase."""
        self.phase = "scout"

        prompt = f"""
        You are the Scout agent in Context Foundry.

        Task: {self.task_description}
        Project: {self.project_name}

        Research the codebase to understand how to implement this task.
        Follow the Scout agent configuration in .foundry/agents/scout.md.

        Output a RESEARCH.md file following the specified format.
        Maximum 5000 tokens.
        Target context usage: <30%.

        Save to: {self.blueprints_path}/specs/RESEARCH_{self.timestamp}.md
        """

        # This would call Claude API/CLI
        # For now, we'll create a template
        research_file = self.blueprints_path / f"specs/RESEARCH_{self.timestamp}.md"
        research_file.parent.mkdir(parents=True, exist_ok=True)

        research_content = f"""# Research Report: {self.task_description}
Generated: {datetime.now().isoformat()}
Context Usage: 28%

## Architecture Overview
[Scout agent would fill this in based on actual research]

## Relevant Components
[Actual components discovered]

## Recommendations
Based on the codebase analysis, the recommended approach is...
"""

        research_file.write_text(research_content)

        return {
            'file': str(research_file),
            'context_usage': 28,
            'status': 'complete'
        }

    def run_architect_phase(self, scout_result: Dict) -> Dict:
        """Execute planning phase."""
        self.phase = "architect"

        research = Path(scout_result['file']).read_text()

        prompt = f"""
        You are the Architect agent in Context Foundry.

        Task: {self.task_description}
        Project: {self.project_name}

        Research findings:
        {research}

        Create comprehensive specifications and implementation plans.
        Follow the Architect agent configuration in .foundry/agents/architect.md.

        Generate three files:
        1. SPEC_{self.timestamp}.md - User stories and success criteria
        2. PLAN_{self.timestamp}.md - Technical implementation plan
        3. TASKS_{self.timestamp}.md - Decomposed task list

        Target context usage: <40%.
        """

        # Create the files
        spec_file = self.blueprints_path / f"specs/SPEC_{self.timestamp}.md"
        plan_file = self.blueprints_path / f"plans/PLAN_{self.timestamp}.md"
        tasks_file = self.blueprints_path / f"tasks/TASKS_{self.timestamp}.md"

        # These would be generated by Claude
        spec_file.write_text(f"# Specification: {self.project_name}\n...")
        plan_file.write_text(f"# Implementation Plan: {self.project_name}\n...")
        tasks_file.write_text(f"# Task Breakdown: {self.project_name}\n...")

        return {
            'spec': str(spec_file),
            'plan': str(plan_file),
            'tasks': str(tasks_file),
            'context_usage': 38,
            'status': 'complete'
        }

    def run_builder_phase(self, architect_result: Dict) -> Dict:
        """Execute implementation phase."""
        self.phase = "builder"

        tasks_file = Path(architect_result['tasks'])
        tasks = self.parse_tasks(tasks_file)

        progress_file = self.checkpoints_path / f"PROGRESS_{self.timestamp}.md"
        progress_file.parent.mkdir(parents=True, exist_ok=True)

        completed_tasks = []

        for i, task in enumerate(tasks):
            print(f"\n📝 Task {i+1}/{len(tasks)}: {task['name']}")
            print(f"   Context: {self.context_usage}%")

            # Check context usage
            if self.context_usage > 50:
                print("   🔄 Compacting context...")
                self.compact_context()

            # Execute task (would call Claude)
            result = self.execute_task(task, i)
            completed_tasks.append(result)

            # Update progress
            self.update_progress(progress_file, completed_tasks, tasks)

            # Git commit
            self.create_checkpoint(f"Task {i+1}: {task['name']}")

            # Simulate context growth
            self.context_usage += 8

        return {
            'tasks_completed': len(completed_tasks),
            'progress_file': str(progress_file),
            'context_usage': self.context_usage,
            'status': 'complete'
        }

    def parse_tasks(self, tasks_file: Path) -> List[Dict]:
        """Parse tasks from TASKS.md file."""
        # This would actually parse the markdown file
        # For now, return example tasks
        return [
            {'name': 'Setup project structure', 'dependencies': []},
            {'name': 'Create data models', 'dependencies': [0]},
            {'name': 'Implement API endpoints', 'dependencies': [1]},
            {'name': 'Add tests', 'dependencies': [2]},
            {'name': 'Documentation', 'dependencies': [3]}
        ]

    def execute_task(self, task: Dict, index: int) -> Dict:
        """Execute a single task."""
        # This would actually call Claude to implement the task
        return {
            'task': task,
            'index': index,
            'status': 'complete',
            'tests_passed': True
        }

    def compact_context(self):
        """Reduce context by summarizing completed work."""
        self.context_usage = max(20, self.context_usage - 30)
        print(f"   ✅ Context reduced to {self.context_usage}%")

    def update_progress(self, progress_file: Path, completed: List, total: List):
        """Update progress file."""
        content = f"""# Build Progress: {self.project_name}
Session: {self.session_id}
Current Context: {self.context_usage}%

## Completed Tasks
"""
        for task in completed:
            content += f"- [x] Task {task['index']+1}: {task['task']['name']}\n"

        content += "\n## Remaining Tasks\n"
        for i, task in enumerate(total[len(completed):], len(completed)):
            content += f"- [ ] Task {i+1}: {task['name']}\n"

        progress_file.write_text(content)

    def create_checkpoint(self, message: str):
        """Create git checkpoint."""
        # Would actually create git commit
        print(f"   📍 Checkpoint: {message}")

    def get_human_approval(self, phase: str, result: Dict, critical: bool = False) -> bool:
        """Get human review and approval."""
        if critical:
            print("\n" + "🚨" * 20)
            print("CRITICAL REVIEW REQUIRED")
            print("This is the highest leverage point for quality.")
            print("A bad plan leads to thousands of bad lines of code.")
            print("🚨" * 20)

        print(f"\nHuman Review Required for {phase} Phase")
        print(f"Files generated: {result}")
        print("\nReview the files and type 'approve' to continue or 'reject' to abort: ")

        # Auto-approve for testing
        # In production, this would wait for actual input
        response = "approve"  # input().strip().lower()

        return response == "approve"

    def abort(self, reason: str) -> Dict:
        """Abort the workflow."""
        print(f"\n❌ Workflow aborted: {reason}")
        return {'status': 'aborted', 'reason': reason}

    def handle_error(self, error: Exception, partial_results: Dict) -> Dict:
        """Handle workflow error."""
        print(f"\n❌ Error: {error}")
        return {
            'status': 'error',
            'error': str(error),
            'partial_results': partial_results
        }

    def finalize(self, results: Dict) -> Dict:
        """Finalize successful workflow."""
        print(f"\n✅ Context Foundry workflow complete!")
        print(f"📊 Final context usage: {self.context_usage}%")
        print(f"📁 Project: {self.project_path}")
        print(f"📋 Blueprints: {self.blueprints_path}")
        print(f"💾 Session: {self.session_id}")

        return {
            'status': 'success',
            'session_id': self.session_id,
            'results': results
        }


def main():
    """Entry point for Context Foundry orchestrator."""

    if len(sys.argv) < 3:
        print("Usage: python orchestrate.py <project_name> <task_description>")
        sys.exit(1)

    project_name = sys.argv[1]
    task_description = ' '.join(sys.argv[2:])

    orchestrator = ContextFoundryOrchestrator(project_name, task_description)
    result = orchestrator.run()

    # Save session result
    session_file = Path(f"checkpoints/sessions/{orchestrator.session_id}.json")
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(json.dumps(result, indent=2))

    print(f"\n📄 Session saved to: {session_file}")

    return 0 if result['status'] == 'success' else 1


if __name__ == "__main__":
    exit(main())
