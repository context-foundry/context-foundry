#!/usr/bin/env python3
"""
Autonomous Context Foundry Orchestrator
Fully automated Scout → Architect → Builder workflow using Claude API
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from ace.claude_integration import get_claude_client
from foundry.patterns.pattern_manager import PatternLibrary
from foundry.patterns.pattern_extractor import PatternExtractor
from ace.pattern_injection import PatternInjector
from tools.analyze_session import SessionAnalyzer
from tools.livestream.broadcaster import EventBroadcaster


class AutonomousOrchestrator:
    """
    Fully autonomous Context Foundry orchestrator.
    Uses Claude API to generate real code, not placeholders.
    """

    def __init__(
        self,
        project_name: str,
        task_description: str,
        autonomous: bool = False,
        project_dir: Optional[Path] = None,
        use_patterns: bool = True,
        enable_livestream: bool = False,
        mode: str = "new",  # "new" or "enhance"
    ):
        self.project_name = project_name
        self.task_description = task_description
        self.autonomous = autonomous  # If True, skip human approvals
        self.use_patterns = use_patterns  # If True, use pattern library
        self.enable_livestream = enable_livestream  # If True, broadcast to livestream
        self.mode = mode  # "new" = build from scratch, "enhance" = modify existing
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Paths
        self.project_dir = project_dir or Path(f"examples/{project_name}")
        self.blueprints_path = Path("blueprints")
        self.checkpoints_path = Path("checkpoints/sessions")
        self.logs_path = Path(f"logs/{self.timestamp}")

        # Create directories
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)

        # Session
        self.session_id = f"{project_name}_{self.timestamp}"

        # Claude client with context management (auto-selects API or CLI)
        self.claude = get_claude_client(
            log_dir=self.logs_path,
            session_id=self.session_id,
            use_context_manager=True
        )

        # Initialize pattern library components
        if self.use_patterns:
            self.pattern_library = PatternLibrary()
            self.pattern_injector = PatternInjector(
                self.pattern_library,
                max_patterns=3,
                min_success_rate=70.0
            )
        else:
            self.pattern_library = None
            self.pattern_injector = None

        # Initialize livestream broadcaster
        if self.enable_livestream:
            self.broadcaster = EventBroadcaster(self.session_id)
            self.broadcaster.phase_change("init", context_percent=0)
            self.broadcaster.log_line(f"Starting {project_name}: {task_description}")
        else:
            self.broadcaster = None

        print(f"🏭 Autonomous Context Foundry")
        print(f"📋 Project: {project_name}")
        print(f"📝 Task: {task_description}")
        print(f"🤖 Mode: {'Autonomous' if autonomous else 'Interactive'}")
        print(f"📚 Patterns: {'Enabled' if use_patterns else 'Disabled'}")
        print(f"📡 Livestream: {'Enabled' if enable_livestream else 'Disabled'}")
        print(f"💾 Session: {self.session_id}\n")

    def run(self) -> Dict:
        """Execute the complete autonomous workflow."""
        results = {}

        try:
            # Phase 1: Scout
            print("🔍 PHASE 1: SCOUT")
            print("-" * 60)
            scout_result = self.run_scout_phase()
            results["scout"] = scout_result

            if not self.autonomous and not self.get_approval("Scout", scout_result):
                return self.abort("Scout phase rejected")

            # Phase 2: Architect
            print("\n📐 PHASE 2: ARCHITECT")
            print("-" * 60)
            architect_result = self.run_architect_phase(scout_result)
            results["architect"] = architect_result

            if not self.autonomous:
                print("\n⚠️  CRITICAL CHECKPOINT: Review the plan!")
                if not self.get_approval("Architect", architect_result, critical=True):
                    return self.abort("Architecture phase rejected")

            # Phase 3: Builder
            print("\n🔨 PHASE 3: BUILDER")
            print("-" * 60)
            builder_result = self.run_builder_phase(architect_result)
            results["builder"] = builder_result

            if not self.autonomous and not self.get_approval("Builder", builder_result):
                return self.abort("Build phase rejected")

            return self.finalize(results)

        except Exception as e:
            return self.handle_error(e, results)

    def run_scout_phase(self) -> Dict:
        """Scout phase: Research architecture and approach."""
        # Load Scout agent config
        scout_config = Path(".foundry/agents/scout.md").read_text()

        # Build prompt
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        prompt = f"""You are the Scout agent in Context Foundry.

Task: {self.task_description}
Project: {self.project_name}
Current date/time: {current_timestamp}

{"This is a NEW project - you're starting from scratch, no existing codebase." if self.mode == "new" else "This is an EXISTING project - scout the codebase and plan targeted changes."}

Your job is to {"research and design the architecture for this project" if self.mode == "new" else "understand the existing codebase and plan how to implement the requested changes"}.

IMPORTANT: You do NOT have file write access. Output your complete response as text.
Do NOT ask for permission to create files. Just provide the full RESEARCH.md content.

{scout_config}

Generate a complete RESEARCH.md following the format in the config.
Focus on:
1. Best architecture for this type of project
2. Technology stack and dependencies
3. Project structure and file organization
4. Data models and storage
5. Implementation patterns
6. Potential challenges

Keep output under 5000 tokens. Be specific and actionable."""

        # Inject relevant patterns if enabled
        pattern_ids = []
        if self.use_patterns and self.pattern_injector:
            prompt, pattern_ids = self.pattern_injector.inject_into_scout_prompt(
                prompt,
                self.project_name,
                self.task_description
            )
            if pattern_ids:
                print(f"📚 Injected {len(pattern_ids)} relevant patterns")

        # Broadcast phase start
        if self.broadcaster:
            self.broadcaster.phase_change("scout", context_percent=0)
            self.broadcaster.log_line("Starting Scout phase: Research and architecture")

        # Call Claude with content type tracking
        self.claude.reset_context()
        response, metadata = self.claude.call_claude(prompt, content_type="decision")

        # Save RESEARCH.md
        research_file = self.blueprints_path / f"specs/RESEARCH_{self.timestamp}.md"
        research_file.parent.mkdir(parents=True, exist_ok=True)
        research_file.write_text(response)

        print(f"✅ Research complete")
        print(f"📄 Saved to: {research_file}")
        print(f"📊 Context: {metadata['context_percentage']}%")

        # Broadcast completion
        if self.broadcaster:
            self.broadcaster.log_line(f"Scout phase complete - {metadata['context_percentage']}% context")
            self.broadcaster.context_update(
                int(metadata.get('context_percentage', 0)),
                metadata.get('total_tokens', 0)
            )

        return {
            "file": str(research_file),
            "content": response,
            "metadata": metadata,
            "status": "complete",
        }

    def run_architect_phase(self, scout_result: Dict) -> Dict:
        """Architect phase: Create specifications and implementation plan."""
        research_content = scout_result["content"]

        # Load Architect agent config
        architect_config = Path(".foundry/agents/architect.md").read_text()

        # Build prompt
        prompt = f"""You are the Architect agent in Context Foundry.

Task: {self.task_description}
Project: {self.project_name}

Research from Scout phase:
{research_content}

IMPORTANT: You do NOT have file write access. Output the complete content of all three files as text.
Do NOT ask for permission to create files. Just provide the full file contents.

{architect_config}

Generate THREE files with comprehensive planning:

1. SPEC.md - Specifications with user stories, success criteria, requirements
2. PLAN.md - Technical implementation plan with architecture decisions, phases, testing strategy
3. TASKS.md - Detailed task breakdown with dependencies and estimated context

Output each file's COMPLETE content. Be thorough and specific. This is the CRITICAL planning phase."""

        # Inject relevant patterns if enabled
        pattern_ids = []
        if self.use_patterns and self.pattern_injector:
            prompt, pattern_ids = self.pattern_injector.inject_into_architect_prompt(
                prompt,
                self.project_name,
                self.task_description,
                research_content
            )
            if pattern_ids:
                print(f"📚 Injected {len(pattern_ids)} relevant patterns")

        # Broadcast phase start
        if self.broadcaster:
            self.broadcaster.phase_change("architect", context_percent=0)
            self.broadcaster.log_line("Starting Architect phase: Creating specifications")

        # Call Claude with fresh context
        self.claude.reset_context()
        response, metadata = self.claude.call_claude(prompt, content_type="decision")

        # Parse response to extract three files
        # For now, save the whole response and prompt user to split
        spec_file = self.blueprints_path / f"specs/SPEC_{self.timestamp}.md"
        plan_file = self.blueprints_path / f"plans/PLAN_{self.timestamp}.md"
        tasks_file = self.blueprints_path / f"tasks/TASKS_{self.timestamp}.md"

        # Simple parsing: look for markdown headers
        files = self._parse_architect_response(response)

        spec_file.write_text(files.get("spec", response))
        plan_file.write_text(files.get("plan", response))
        tasks_file.write_text(files.get("tasks", response))

        print(f"✅ Architecture complete")
        print(f"📄 SPEC: {spec_file}")
        print(f"📄 PLAN: {plan_file}")
        print(f"📄 TASKS: {tasks_file}")
        print(f"📊 Context: {metadata['context_percentage']}%")

        # Broadcast completion
        if self.broadcaster:
            self.broadcaster.log_line(f"Architect phase complete - {metadata['context_percentage']}% context")
            self.broadcaster.context_update(
                int(metadata.get('context_percentage', 0)),
                metadata.get('total_tokens', 0)
            )

        return {
            "spec": str(spec_file),
            "plan": str(plan_file),
            "tasks": str(tasks_file),
            "metadata": metadata,
            "status": "complete",
        }

    def run_builder_phase(self, architect_result: Dict) -> Dict:
        """Builder phase: Implement code task by task."""
        # Load tasks
        tasks_file = Path(architect_result["tasks"])
        tasks_content = tasks_file.read_text()

        # Parse tasks (simplified - look for ### Task headers)
        tasks = self._parse_tasks(tasks_content)

        print(f"Found {len(tasks)} tasks to implement\n")

        # Broadcast phase start
        if self.broadcaster:
            self.broadcaster.phase_change("builder", context_percent=0)
            self.broadcaster.log_line(f"Starting Builder phase: {len(tasks)} tasks")

        completed_tasks = []
        progress_file = self.checkpoints_path / f"PROGRESS_{self.timestamp}.md"
        progress_file.parent.mkdir(parents=True, exist_ok=True)

        for i, task in enumerate(tasks, 1):
            print(f"📝 Task {i}/{len(tasks)}: {task['name']}")

            # Broadcast task start
            if self.broadcaster:
                self.broadcaster.log_line(f"Task {i}/{len(tasks)}: {task['name']}")

            # Check context usage - compaction is now automatic in ClaudeClient
            stats = self.claude.get_context_stats()
            context_pct = stats.get('context_percentage', 0)
            print(f"   Context: {context_pct:.1f}%")

            # Broadcast context update
            if self.broadcaster:
                self.broadcaster.context_update(int(context_pct), stats.get('total_tokens', 0))

            # Show context health if available
            if 'context_health' in stats:
                print(f"   Health: {stats['context_health']}")
                if stats.get('compaction_stats', {}).get('count', 0) > 0:
                    print(f"   Compactions: {stats['compaction_stats']['count']}")

            # Build task prompt
            task_prompt = f"""You are the Builder agent implementing Task {i} of {len(tasks)}.

Task: {task['name']}
Description: {task.get('description', '')}
Files: {', '.join(task.get('files', []))}

Instructions:
1. Write comprehensive tests FIRST (TDD approach)
2. Then implement the functionality
3. Use proper type hints and docstrings
4. Ensure all tests pass

Project: {self.project_name}
Project directory: {self.project_dir}

CRITICAL INSTRUCTIONS:
1. You do NOT have file write access or tools
2. Do NOT ask for permission to create files
3. You MUST output actual code files as text, not descriptions
4. Output COMPLETE file contents in markdown code blocks

Use this EXACT format for each file:

File: backend/main.py
```python
# Actual complete code goes here
import something

def main():
    pass
```

File: frontend/index.html
```html
<!DOCTYPE html>
<html>
...complete actual HTML...
</html>
```

DO NOT:
- Ask "May I create these files?"
- Just list or describe files
- Use Write/Edit tools (you don't have them)

DO:
- Output COMPLETE working code for every file
- Include all imports, functions, classes
- Provide production-ready code"""

            # Inject relevant patterns if enabled
            pattern_ids = []
            if self.use_patterns and self.pattern_injector:
                task_prompt, pattern_ids = self.pattern_injector.inject_into_builder_prompt(
                    task_prompt,
                    self.project_name,
                    task['name'],
                    ""  # spec context
                )
                if pattern_ids:
                    print(f"   📚 Using {len(pattern_ids)} patterns")

            # Call Claude with code content type
            response, metadata = self.claude.call_claude(task_prompt, content_type="code")

            # Save task output
            task_output = self.logs_path / f"task_{i}_output.md"
            task_output.write_text(response)

            # Extract and save code files
            self._extract_and_save_code(response, self.project_dir)

            print(f"   ✅ Task {i} complete")
            print(f"   📄 Output: {task_output}")

            # Broadcast task completion
            if self.broadcaster:
                self.broadcaster.task_complete(task['name'], int(metadata.get('context_percentage', 0)))

            # Update progress
            completed_tasks.append(
                {
                    "task": i,
                    "name": task["name"],
                    "status": "complete",
                    "context": metadata["context_percentage"],
                }
            )

            self._update_progress(progress_file, completed_tasks, tasks)

            # Git commit
            if self._git_available():
                self._create_git_commit(
                    f"Task {i}: {task['name']}\n\nContext: {metadata['context_percentage']}%"
                )

        return {
            "tasks_completed": len(completed_tasks),
            "progress_file": str(progress_file),
            "metadata": self.claude.get_context_stats(),
            "status": "complete",
        }

    def _parse_architect_response(self, response: str) -> Dict[str, str]:
        """Parse architect response to extract SPEC, PLAN, TASKS."""
        files = {}

        # Simple parsing - look for markdown code blocks or headers
        # This is a simplified version - production would be more robust
        if "# Specification:" in response:
            spec_start = response.find("# Specification:")
            spec_end = response.find("# Implementation Plan:", spec_start)
            if spec_end > spec_start:
                files["spec"] = response[spec_start:spec_end].strip()

        if "# Implementation Plan:" in response:
            plan_start = response.find("# Implementation Plan:")
            plan_end = response.find("# Task Breakdown:", plan_start)
            if plan_end > plan_start:
                files["plan"] = response[plan_start:plan_end].strip()

        if "# Task Breakdown:" in response:
            tasks_start = response.find("# Task Breakdown:")
            files["tasks"] = response[tasks_start:].strip()

        # Fallback: if parsing failed, use whole response
        if not files:
            files = {"spec": response, "plan": response, "tasks": response}

        return files

    def _parse_tasks(self, tasks_content: str) -> List[Dict]:
        """Parse TASKS.md to extract individual tasks."""
        tasks = []

        # Simple parsing: look for ### Task headers
        lines = tasks_content.split("\n")
        current_task = None

        for line in lines:
            if line.startswith("### Task"):
                if current_task:
                    tasks.append(current_task)

                # Extract task name
                task_name = line.replace("### Task", "").strip()
                current_task = {"name": task_name, "description": "", "files": []}

            elif current_task and line.startswith("- **Files**:"):
                # Extract files
                files_str = line.replace("- **Files**:", "").strip()
                current_task["files"] = [f.strip() for f in files_str.split(",")]

            elif current_task and line.startswith("- **Changes**:"):
                current_task["description"] = line.replace("- **Changes**:", "").strip()

        if current_task:
            tasks.append(current_task)

        # Fallback: if no tasks parsed, create a single task
        if not tasks:
            tasks = [
                {
                    "name": "Implement project",
                    "description": "Complete implementation",
                    "files": [],
                }
            ]

        return tasks

    def _extract_and_save_code(self, response: str, project_dir: Path):
        """Extract code blocks from response and save to files."""
        import re

        # Try multiple patterns to be flexible
        patterns = [
            # Pattern 1: "File: path" followed by code block
            r"File:\s*([^\n]+)\n```(?:\w+)?\n(.*?)```",
            # Pattern 2: "file: path" (lowercase)
            r"file:\s*([^\n]+)\n```(?:\w+)?\n(.*?)```",
            # Pattern 3: "File path: path"
            r"File path:\s*([^\n]+)\n```(?:\w+)?\n(.*?)```",
            # Pattern 4: Just a path in backticks before code block
            r"`([^`\n]+\.[a-z]{2,4})`\n```(?:\w+)?\n(.*?)```",
        ]

        files_created = 0

        for pattern in patterns:
            matches = re.finditer(pattern, response, re.DOTALL | re.IGNORECASE)

            for match in matches:
                filepath = match.group(1).strip()
                code = match.group(2).strip()

                # Clean up filepath
                filepath = filepath.replace("`", "").strip()

                # Skip if filepath looks like description text
                if len(filepath) > 100 or '\n' in filepath:
                    continue

                # Save file
                full_path = project_dir / filepath
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(code)

                print(f"   📁 Created: {full_path}")
                files_created += 1

        if files_created == 0:
            print(f"   ⚠️  WARNING: No code files were extracted from Builder output!")
            print(f"   💡 Check: logs/{self.timestamp}/task_*_output.md")
            print(f"   The LLM may have described files instead of outputting code.")

    def _update_progress(
        self, progress_file: Path, completed: List[Dict], total: List[Dict]
    ):
        """Update progress tracking file."""
        stats = self.claude.get_context_stats()

        content = f"""# Build Progress: {self.project_name}
Session: {self.session_id}
Current Context: {stats['context_percentage']}%
Total Tokens: {stats['total_tokens']:,}

## Completed Tasks
"""
        for task in completed:
            content += f"- [x] Task {task['task']}: {task['name']} (Context: {task['context']}%)\n"

        content += "\n## Remaining Tasks\n"
        for i, task in enumerate(total[len(completed) :], len(completed) + 1):
            content += f"- [ ] Task {i}: {task['name']}\n"

        progress_file.write_text(content)

    def _git_available(self) -> bool:
        """Check if git is available and initialized."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except:
            return False

    def _create_git_commit(self, message: str):
        """Create a git commit for current changes."""
        try:
            subprocess.run(["git", "add", "."], check=True, timeout=10)
            subprocess.run(
                ["git", "commit", "-m", message], check=True, timeout=10
            )
            print(f"   📍 Git commit created")
        except Exception as e:
            print(f"   ⚠️  Git commit failed: {e}")

    def get_approval(
        self, phase: str, result: Dict, critical: bool = False
    ) -> bool:
        """Get human approval for phase."""
        if critical:
            print("\n" + "🚨" * 30)
            print("CRITICAL CHECKPOINT - REVIEW REQUIRED")
            print("Bad plan = thousands of bad lines of code")
            print("🚨" * 30)

        while True:
            print(f"\n✋ Human Review Required: {phase} Phase")
            print(f"📄 Files: {result}")
            approval = input("\nType 'approve' to continue, anything else to abort: ")

            if approval.lower() == "approve":
                return True

            # Confirmation before aborting
            print(f"\n⚠️  You typed: '{approval}'")
            confirm = input("Are you sure you want to abort? (yes/no): ")

            if confirm.lower() in ('yes', 'y'):
                return False
            else:
                print("\n💡 Tip: Type 'approve' (exactly) to continue")
                # Loop back to ask for approval again

    def abort(self, reason: str) -> Dict:
        """Abort workflow."""
        print(f"\n❌ Workflow aborted: {reason}")
        return {"status": "aborted", "reason": reason}

    def handle_error(self, error: Exception, partial_results: Dict) -> Dict:
        """Handle workflow error."""
        print(f"\n❌ Error: {error}")
        import traceback

        traceback.print_exc()

        return {
            "status": "error",
            "error": str(error),
            "partial_results": partial_results,
        }

    def finalize(self, results: Dict) -> Dict:
        """Finalize successful workflow."""
        stats = self.claude.get_context_stats()

        print(f"\n{'='*60}")
        print("✅ CONTEXT FOUNDRY WORKFLOW COMPLETE!")
        print(f"{'='*60}")
        print(f"📁 Project: {self.project_dir}")
        print(f"📊 Total Tokens: {stats['total_tokens']:,}")
        print(f"💾 Logs: {self.logs_path}")
        print(f"🎯 Session: {self.session_id}")

        # Save final conversation
        self.claude.save_full_conversation(self.logs_path / "full_conversation.json")

        # Save session summary
        session_file = self.checkpoints_path / f"{self.session_id}.json"
        session_file.write_text(json.dumps(results, indent=2))

        # Extract patterns from successful build
        if self.use_patterns and self.pattern_library:
            print("\n🔍 Extracting patterns from successful build...")
            try:
                extractor = PatternExtractor(self.pattern_library)
                patterns_extracted = extractor.extract_from_session(self.project_dir)
                print(f"   ✅ Extracted {patterns_extracted} new patterns")
            except Exception as e:
                print(f"   ⚠️  Pattern extraction failed: {e}")

        # Run session analysis
        print("\n📊 Analyzing session...")
        try:
            analyzer = SessionAnalyzer(
                pattern_library=self.pattern_library if self.use_patterns else None
            )
            metrics = analyzer.analyze(self.session_id, self.checkpoints_path.parent)

            if metrics:
                print(f"   ✅ Analysis complete")
                print(f"   📄 Report: {metrics.get('report_path', 'N/A')}")
                print(f"   📈 Completion: {metrics.get('completion', {}).get('rate', 0):.1f}%")
                print(f"   💰 Cost: ${metrics.get('cost', 0):.2f}")

                # Add metrics to results
                results['metrics'] = metrics
        except Exception as e:
            print(f"   ⚠️  Session analysis failed: {e}")

        # Close pattern library
        if self.pattern_library:
            self.pattern_library.close()

        # Broadcast completion
        if self.broadcaster:
            self.broadcaster.phase_change("complete", context_percent=0)
            self.broadcaster.completion(
                success=True,
                summary={
                    "tasks_completed": results.get("builder", {}).get("tasks_completed", 0),
                    "total_tokens": stats.get("total_tokens", 0),
                    "session_id": self.session_id
                }
            )

        return {"status": "success", "session_id": self.session_id, "results": results}


def main():
    """CLI entry point."""
    if len(sys.argv) < 3:
        print("Usage: python autonomous_orchestrator.py <project_name> <task_description> [--autonomous]")
        print()
        print("Examples:")
        print('  python autonomous_orchestrator.py todo-app "Build CLI todo app"')
        print('  python autonomous_orchestrator.py api-server "REST API with auth" --autonomous')
        sys.exit(1)

    project_name = sys.argv[1]
    task_description = " ".join(sys.argv[2:])
    autonomous = "--autonomous" in sys.argv

    if autonomous:
        task_description = task_description.replace("--autonomous", "").strip()

    orchestrator = AutonomousOrchestrator(project_name, task_description, autonomous)
    result = orchestrator.run()

    exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
