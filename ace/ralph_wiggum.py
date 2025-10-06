#!/usr/bin/env python3
"""
Ralph Wiggum Runner - Continuous Loop Strategy
Implements Jeff Huntley's approach: Same prompt, fresh context, persistent progress

Named after Ralph from The Simpsons - keeps going with fresh enthusiasm each time!
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))

from ace.claude_integration import ClaudeClient
from foundry.patterns.pattern_manager import PatternLibrary
from foundry.patterns.pattern_extractor import PatternExtractor
from ace.pattern_injection import PatternInjector
from tools.analyze_session import SessionAnalyzer
from tools.livestream.broadcaster import EventBroadcaster


class RalphWiggumRunner:
    """
    Implements the continuous loop strategy for overnight coding.

    Strategy:
    1. Load progress from previous iterations
    2. Reset Claude context (fresh start)
    3. Run one iteration with full task context
    4. Save progress
    5. Check if task is complete
    6. Repeat until done or max iterations

    The key insight: Same prompt, fresh context, but progress persists via files.
    """

    def __init__(
        self,
        project_name: str,
        task_description: str,
        session_id: str,
    ):
        self.project_name = project_name
        self.task_description = task_description
        self.session_id = session_id

        # Paths
        self.checkpoint_dir = Path(f"checkpoints/ralph/{session_id}")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self.progress_file = self.checkpoint_dir / "progress.json"
        self.state_file = self.checkpoint_dir / "state.json"
        self.completion_flag = self.checkpoint_dir / "COMPLETE"

        # Project directory
        self.project_dir = Path(f"examples/{project_name}")
        self.project_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Claude client with context management
        self.claude = ClaudeClient(
            log_dir=Path(f"logs/ralph_{session_id}"),
            session_id=session_id,
            use_context_manager=True
        )

        # Initialize pattern library components
        self.pattern_library = PatternLibrary()
        self.pattern_injector = PatternInjector(
            self.pattern_library,
            max_patterns=3,
            min_success_rate=70.0
        )

        # Initialize livestream broadcaster
        self.broadcaster = EventBroadcaster(self.session_id)
        self.broadcaster.phase_change("init", context_percent=0)
        self.broadcaster.log_line(f"Ralph Wiggum session started: {project_name}")

        # Load or initialize state
        self.state = self.load_state()

    def load_state(self) -> Dict:
        """Load state from previous iteration or create new."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)

        # Initialize new state
        return {
            "project_name": self.project_name,
            "task_description": self.task_description,
            "session_id": self.session_id,
            "start_time": datetime.now().isoformat(),
            "iterations": 0,
            "completed_tasks": [],
            "failed_attempts": [],
            "current_phase": "scout",  # scout, architect, builder
            "artifacts": {},
        }

    def save_state(self):
        """Save current state to checkpoint."""
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def load_progress(self) -> Dict:
        """Load progress from previous iterations."""
        if self.progress_file.exists():
            with open(self.progress_file) as f:
                return json.load(f)
        return {"completed": [], "remaining": [], "notes": []}

    def save_progress(self, progress: Dict):
        """Save progress for next iteration."""
        with open(self.progress_file, "w") as f:
            json.dump(progress, f, indent=2)

    def reset_context(self):
        """
        Reset Claude context for fresh iteration.
        This is the Ralph Wiggum magic: "I'm starting fresh!"
        """
        self.claude.reset_context()
        print("🔄 Context reset - fresh iteration starting")

    def check_completion(self) -> Tuple[bool, str]:
        """
        Check if task is complete.

        Returns:
            (is_complete, reason)
        """
        # Check completion flag file
        if self.completion_flag.exists():
            return True, "Completion flag file exists"

        # Check if we have all required artifacts
        required_artifacts = ["research", "spec", "plan", "tasks"]
        has_all_artifacts = all(
            self.state["artifacts"].get(art) for art in required_artifacts
        )

        if not has_all_artifacts:
            return False, "Missing required artifacts"

        # Check if builder phase completed
        if self.state["current_phase"] == "complete":
            return True, "Builder phase marked as complete"

        # Check progress
        progress = self.load_progress()
        if progress.get("completed") and not progress.get("remaining"):
            return True, "All tasks completed"

        return False, "Tasks still remaining"

    def estimate_remaining(self) -> str:
        """Estimate time remaining based on progress."""
        progress = self.load_progress()
        completed = len(progress.get("completed", []))
        remaining = len(progress.get("remaining", []))

        if completed == 0:
            return "Unknown (no completed tasks yet)"

        # Average time per task
        iterations = self.state["iterations"]
        if iterations > 0:
            avg_iterations_per_task = iterations / completed
            estimated_iterations = avg_iterations_per_task * remaining
            estimated_minutes = estimated_iterations * 5  # ~5 min per iteration

            return f"~{int(estimated_minutes)} minutes ({int(estimated_iterations)} iterations)"

        return f"{remaining} tasks remaining"

    def run_iteration(self, iteration: int) -> Dict:
        """
        Run one complete iteration of the task.

        This is where the magic happens:
        1. Load what we've done
        2. Ask Claude to continue from there
        3. Save the results
        """
        self.state["iterations"] = iteration
        self.state["last_iteration_time"] = datetime.now().isoformat()

        print(f"🔄 Iteration {iteration}")
        print(f"📊 Current phase: {self.state['current_phase']}")

        # Broadcast iteration start
        self.broadcaster.iteration_start(iteration)
        self.broadcaster.log_line(f"Iteration {iteration} - Phase: {self.state['current_phase']}")

        # Load progress
        progress = self.load_progress()

        # Reset context for fresh start
        self.reset_context()

        # Build context-aware prompt
        prompt = self._build_iteration_prompt(progress)

        # Inject relevant patterns based on phase
        pattern_ids = []
        if self.state['current_phase'] == "scout":
            prompt, pattern_ids = self.pattern_injector.inject_into_scout_prompt(
                prompt, self.project_name, self.task_description
            )
        elif self.state['current_phase'] == "architect":
            research = self.state.get("artifacts", {}).get("research", "")
            prompt, pattern_ids = self.pattern_injector.inject_into_architect_prompt(
                prompt, self.project_name, self.task_description, research
            )
        elif self.state['current_phase'] == "builder":
            spec = self.state.get("artifacts", {}).get("spec", "")
            prompt, pattern_ids = self.pattern_injector.inject_into_builder_prompt(
                prompt, self.project_name, "Continue implementation", spec
            )

        if pattern_ids:
            print(f"📚 Injected {len(pattern_ids)} relevant patterns")
            self.broadcaster.log_line(f"Using {len(pattern_ids)} patterns")

        # Broadcast phase change if needed
        current_phase = self.state['current_phase']
        if self.state.get('last_phase') != current_phase:
            self.broadcaster.phase_change(current_phase, context_percent=0)
            self.state['last_phase'] = current_phase

        # Determine content type based on phase
        content_type_map = {
            "scout": "decision",
            "architect": "decision",
            "builder": "code",
            "complete": "general"
        }
        content_type = content_type_map.get(self.state['current_phase'], "general")

        # Call Claude with content type
        print("🤖 Calling Claude API...")
        response, metadata = self.claude.call_claude(prompt, content_type=content_type)

        # Broadcast context update
        self.broadcaster.context_update(
            int(metadata.get('context_percentage', 0)),
            metadata.get('total_tokens', 0)
        )

        # Process response
        result = self._process_response(response, metadata)

        # Update state
        self.state["artifacts"].update(result.get("artifacts", {}))

        # Save state
        self.save_state()

        print(f"✅ Iteration {iteration} complete")
        print(f"📊 Context usage: {metadata['context_percentage']:.1f}%")

        # Broadcast iteration complete
        self.broadcaster.iteration_complete(iteration, int(metadata.get('context_percentage', 0)))

        # Show context health if available
        if 'context_health' in metadata:
            print(f"📊 Context health: {metadata['context_health']}")
            if metadata.get('compaction_count', 0) > 0:
                print(f"🔄 Compactions performed: {metadata['compaction_count']}")

        return result

    def _build_iteration_prompt(self, progress: Dict) -> str:
        """
        Build prompt for this iteration that includes progress context.
        """
        phase = self.state["current_phase"]

        # Base context
        context = f"""You are working on: {self.task_description}
Project: {self.project_name}
Session: {self.session_id}

This is iteration {self.state['iterations']} of a continuous coding session.
"""

        # Add progress context
        if progress.get("completed"):
            context += f"\n✅ Completed tasks:\n"
            for task in progress["completed"]:
                context += f"  - {task}\n"

        if progress.get("remaining"):
            context += f"\n📋 Remaining tasks:\n"
            for task in progress["remaining"]:
                context += f"  - {task}\n"

        if progress.get("notes"):
            context += f"\n📝 Notes from previous iterations:\n"
            for note in progress["notes"][-3:]:  # Last 3 notes
                context += f"  - {note}\n"

        # Phase-specific instructions
        if phase == "scout":
            context += self._get_scout_instructions()
        elif phase == "architect":
            context += self._get_architect_instructions()
        elif phase == "builder":
            context += self._get_builder_instructions()

        return context

    def _get_scout_instructions(self) -> str:
        """Get instructions for scout phase."""
        return """
CURRENT PHASE: SCOUT (Research)

Your task:
1. Research how to build this project from scratch
2. Design the architecture
3. Identify required technologies
4. Create a complete RESEARCH.md file

Output format: Provide a complete RESEARCH.md with architecture, tech stack, file structure, and implementation approach.

Be thorough and specific. This research will guide all subsequent work.
"""

    def _get_architect_instructions(self) -> str:
        """Get instructions for architect phase."""
        research = self.state["artifacts"].get("research", "")

        return f"""
CURRENT PHASE: ARCHITECT (Planning)

Previous research:
{research}

Your task:
1. Create SPEC.md with user stories and success criteria
2. Create PLAN.md with technical approach and architecture decisions
3. Create TASKS.md with detailed task breakdown

Break down into atomic, testable tasks. Each task should be completable in one iteration.

Output all three files.
"""

    def _get_builder_instructions(self) -> str:
        """Get instructions for builder phase."""
        progress = self.load_progress()

        if not progress.get("remaining"):
            return "\nAll tasks complete! Mark session as COMPLETE."

        next_task = progress["remaining"][0] if progress["remaining"] else None

        if not next_task:
            return "\nNo remaining tasks found. Review and mark complete if done."

        return f"""
CURRENT PHASE: BUILDER (Implementation)

Next task to implement: {next_task}

Your task:
1. Write tests FIRST (TDD)
2. Implement the functionality
3. Ensure all tests pass
4. Include complete file contents with paths

After this task, we'll move to the next one.

Generate complete, working code.
"""

    def _process_response(self, response: str, metadata: Dict) -> Dict:
        """Process Claude's response and extract artifacts."""
        result = {"artifacts": {}, "phase_complete": False}

        # Simple artifact extraction
        if "# Research Report:" in response or "RESEARCH.md" in response:
            result["artifacts"]["research"] = response
            self.state["current_phase"] = "architect"
            result["phase_complete"] = True

        elif "SPEC.md" in response and "PLAN.md" in response and "TASKS.md" in response:
            result["artifacts"]["spec"] = response
            result["artifacts"]["plan"] = response
            result["artifacts"]["tasks"] = response

            # Extract tasks for progress tracking
            tasks = self._extract_tasks(response)
            progress = {"completed": [], "remaining": tasks, "notes": []}
            self.save_progress(progress)

            self.state["current_phase"] = "builder"
            result["phase_complete"] = True

        elif "```python" in response or "```javascript" in response:
            # Builder phase - code generated
            self._save_code_files(response)

            # Update progress
            progress = self.load_progress()
            if progress["remaining"]:
                completed_task = progress["remaining"].pop(0)
                progress["completed"].append(completed_task)
                progress["notes"].append(
                    f"Completed {completed_task} at iteration {self.state['iterations']}"
                )
                self.save_progress(progress)

            # Check if all tasks done
            if not progress["remaining"]:
                self.state["current_phase"] = "complete"
                self.completion_flag.touch()
                result["phase_complete"] = True

        return result

    def _extract_tasks(self, response: str) -> List[str]:
        """Extract task list from TASKS.md."""
        tasks = []
        lines = response.split("\n")

        for line in lines:
            # Look for task headers
            if line.startswith("### Task"):
                # Extract task name
                task_name = line.replace("### Task", "").strip()
                if task_name:
                    tasks.append(task_name)

        return tasks if tasks else ["Implement complete project"]

    def _save_code_files(self, response: str):
        """Extract and save code files from response."""
        import re

        # Look for file paths and code blocks
        # Fixed: Allow optional whitespace/newline after language identifier
        pattern = r"(?:File|file|File path):\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```"
        matches = re.finditer(pattern, response, re.DOTALL)

        for match in matches:
            filepath = match.group(1).strip().replace("`", "")
            code = match.group(2).strip()

            full_path = self.project_dir / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(code)

            print(f"   📁 Saved: {full_path}")

    def run_until_complete(
        self, max_hours: int = 24, max_iterations: int = 100
    ) -> Dict:
        """
        Run iterations until task is complete or limits reached.

        This is typically called by overnight_session.sh, but can be used standalone.
        """
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=max_hours)

        iteration = self.state["iterations"]

        while iteration < max_iterations:
            iteration += 1

            # Check time limit
            if datetime.now() >= end_time:
                print(f"⏰ Time limit reached ({max_hours} hours)")
                break

            # Check if already complete
            is_complete, reason = self.check_completion()
            if is_complete:
                print(f"✅ Task complete: {reason}")
                break

            # Run iteration
            try:
                result = self.run_iteration(iteration)

                # Check completion after iteration
                is_complete, reason = self.check_completion()
                if is_complete:
                    print(f"🎉 Task completed! {reason}")
                    break

            except Exception as e:
                print(f"❌ Error in iteration {iteration}: {e}")
                self.state["failed_attempts"].append(
                    {"iteration": iteration, "error": str(e), "time": datetime.now().isoformat()}
                )
                self.save_state()

                # Don't break on errors - Ralph keeps trying!
                import time
                time.sleep(30)  # Wait before retry

        # Final stats
        duration = datetime.now() - start_time
        print(f"\n📊 Session complete:")
        print(f"   Iterations: {iteration}")
        print(f"   Duration: {duration}")
        print(f"   Phase: {self.state['current_phase']}")

        is_complete, _ = self.check_completion()

        # If complete, extract patterns and analyze
        if is_complete:
            print("\n🔍 Extracting patterns from successful build...")
            try:
                extractor = PatternExtractor(self.pattern_library)
                patterns_extracted = extractor.extract_from_session(self.project_dir)
                print(f"   ✅ Extracted {patterns_extracted} new patterns")
            except Exception as e:
                print(f"   ⚠️  Pattern extraction failed: {e}")

            print("\n📊 Analyzing session...")
            try:
                analyzer = SessionAnalyzer(pattern_library=self.pattern_library)
                metrics = analyzer.analyze(self.session_id, self.checkpoint_dir.parent)

                if metrics:
                    print(f"   ✅ Analysis complete")
                    print(f"   📄 Report: {metrics.get('report_path', 'N/A')}")
                    print(f"   📈 Completion: {metrics.get('completion', {}).get('rate', 0):.1f}%")
                    print(f"   💰 Cost: ${metrics.get('cost', 0):.2f}")
            except Exception as e:
                print(f"   ⚠️  Session analysis failed: {e}")

        # Close pattern library
        if self.pattern_library:
            self.pattern_library.close()

        # Broadcast final completion
        if is_complete:
            self.broadcaster.phase_change("complete", context_percent=0)
            self.broadcaster.completion(
                success=True,
                summary={
                    "iterations": iteration,
                    "duration_seconds": duration.total_seconds(),
                    "phase": self.state["current_phase"]
                }
            )

        return {
            "complete": is_complete,
            "iterations": iteration,
            "duration_seconds": duration.total_seconds(),
            "final_phase": self.state["current_phase"],
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Ralph Wiggum - Continuous Loop Runner")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--task", required=True, help="Task description")
    parser.add_argument("--session", required=True, help="Session ID")
    parser.add_argument("--iteration", type=int, default=1, help="Current iteration number")
    parser.add_argument(
        "--continuous", action="store_true", help="Run continuously until complete"
    )

    args = parser.parse_args()

    runner = RalphWiggumRunner(
        project_name=args.project, task_description=args.task, session_id=args.session
    )

    if args.continuous:
        # Run until complete
        result = runner.run_until_complete()
        sys.exit(0 if result["complete"] else 1)
    else:
        # Run single iteration (called by overnight_session.sh)
        try:
            runner.run_iteration(args.iteration)

            # Check if complete
            is_complete, reason = runner.check_completion()

            if is_complete:
                print(f"✅ {reason}")
                sys.exit(42)  # Special exit code: task complete

            sys.exit(0)

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(99)  # Special exit code: unrecoverable error


if __name__ == "__main__":
    main()
