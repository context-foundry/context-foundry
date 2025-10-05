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
from typing import Dict, List, Optional, Any

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from ace.claude_integration import get_claude_client
from ace.pricing_database import PricingDatabase
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
        ctx: Optional[Any] = None,  # FastMCP Context for MCP mode
        auto_push: bool = False,  # If True, push to GitHub after successful build
    ):
        self.project_name = project_name
        self.task_description = task_description
        self.autonomous = autonomous  # If True, skip human approvals
        self.use_patterns = use_patterns  # If True, use pattern library
        self.enable_livestream = enable_livestream  # If True, broadcast to livestream
        self.mode = mode  # "new" = build from scratch, "enhance" = modify existing, "fix" = repair issues
        self.ctx = ctx  # Store MCP context
        self.auto_push = auto_push  # If True, push to GitHub after build
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # For fix mode session resume
        self.resume_session = None  # Session ID to resume
        self.resume_tasks = None  # List of task numbers to re-run

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

        # Claude client with context management (auto-selects API or MCP mode)
        # If ctx is provided, it will use MCP mode
        self.claude = get_claude_client(
            log_dir=self.logs_path,
            session_id=self.session_id,
            use_context_manager=True,
            prefer_mcp=ctx is not None,  # Use MCP if ctx provided
            ctx=ctx
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
        print(f"📤 Auto-push: {'Enabled' if auto_push else 'Disabled'}")
        print(f"💾 Session: {self.session_id}\n")

    def _format_phase_header(self, phase_name: str, emoji: str, env_provider_var: str, env_model_var: str) -> str:
        """
        Format phase header with agent name, model, and pricing info.

        Args:
            phase_name: Name of phase (e.g., "1: SCOUT", "2: ARCHITECT", "3: BUILDER")
            emoji: Emoji for the phase
            env_provider_var: Environment variable name for provider (e.g., "SCOUT_PROVIDER")
            env_model_var: Environment variable name for model (e.g., "SCOUT_MODEL")

        Returns:
            Formatted header string
        """
        provider = os.getenv(env_provider_var, 'anthropic')
        model = os.getenv(env_model_var, 'claude-sonnet-4-20250514')

        # Get pricing info
        pricing_db = PricingDatabase()
        pricing = pricing_db.get_pricing(provider, model)

        if pricing:
            pricing_str = f"${pricing.input_cost_per_1m:.2f}/1M in, ${pricing.output_cost_per_1m:.2f}/1M out"
        else:
            pricing_str = "pricing unavailable"

        return f"{emoji} PHASE {phase_name} Agent ({provider.title()} {model} | {pricing_str})"

    def run(self) -> Dict:
        """Execute the complete autonomous workflow."""
        results = {}

        try:
            # Check if we're in session resume mode (fix mode with existing session)
            if self.mode == "fix" and self.resume_session and self.resume_tasks:
                return self.run_session_resume()

            # Normal workflow: Scout → Architect → Builder
            # Phase 1: Scout
            header = self._format_phase_header("1: SCOUT", "🔍", "SCOUT_PROVIDER", "SCOUT_MODEL")
            print(header)
            print("-" * 60)
            scout_result = self.run_scout_phase()
            results["scout"] = scout_result

            if not self.autonomous and not self.get_approval("Scout", scout_result):
                return self.abort("Scout phase rejected")

            # Phase 2: Architect
            header = self._format_phase_header("2: ARCHITECT", "📐", "ARCHITECT_PROVIDER", "ARCHITECT_MODEL")
            print(f"\n{header}")
            print("-" * 60)
            architect_result = self.run_architect_phase(scout_result)
            results["architect"] = architect_result

            if not self.autonomous:
                print("\n⚠️  CRITICAL CHECKPOINT: Review the plan!")
                if not self.get_approval("Architect", architect_result, critical=True):
                    return self.abort("Architecture phase rejected")

            # Phase 3: Builder
            header = self._format_phase_header("3: BUILDER", "🔨", "BUILDER_PROVIDER", "BUILDER_MODEL")
            print(f"\n{header}")
            print("-" * 60)
            builder_result = self.run_builder_phase(architect_result)
            results["builder"] = builder_result

            return self.finalize(results)

        except Exception as e:
            return self.handle_error(e, results)

    def run_session_resume(self) -> Dict:
        """Resume a previous session and re-run specific tasks."""
        print(f"🔄 SESSION RESUME MODE")
        print(f"{'='*60}")
        print(f"Session: {self.project_name}_{self.resume_session}")
        print(f"Re-running tasks: {self.resume_tasks}")
        print(f"{'='*60}\n")

        results = {}

        try:
            # Load existing blueprints
            tasks_file = self.blueprints_path / f"tasks/TASKS_{self.resume_session}.md"
            spec_file = self.blueprints_path / f"specs/SPEC_{self.resume_session}.md"
            plan_file = self.blueprints_path / f"plans/PLAN_{self.resume_session}.md"

            if not tasks_file.exists():
                raise FileNotFoundError(
                    f"Session tasks file not found: {tasks_file}\n"
                    f"Cannot resume session {self.resume_session}"
                )

            print(f"✓ Loaded tasks from: {tasks_file}")
            if spec_file.exists():
                print(f"✓ Loaded spec from: {spec_file}")
            if plan_file.exists():
                print(f"✓ Loaded plan from: {plan_file}")

            # Parse tasks
            tasks_content = tasks_file.read_text()
            all_tasks = self._parse_tasks(tasks_content)

            print(f"\n📋 Total tasks in session: {len(all_tasks)}")
            print(f"🎯 Re-running: {len(self.resume_tasks)} tasks\n")

            # Filter to only the tasks we want to re-run
            tasks_to_run = []
            for task_num in self.resume_tasks:
                if 1 <= task_num <= len(all_tasks):
                    tasks_to_run.append(all_tasks[task_num - 1])
                else:
                    print(f"⚠️  Warning: Task {task_num} not found (only {len(all_tasks)} tasks exist)")

            if not tasks_to_run:
                return self.abort("No valid tasks to run")

            # Re-run the Builder phase with only these tasks
            print(f"🔨 BUILDER PHASE (Task Resume)")
            print("-" * 60)

            # Create a minimal architect_result for compatibility
            architect_result = {
                "tasks": str(tasks_file),
                "spec": str(spec_file) if spec_file.exists() else None,
                "plan": str(plan_file) if plan_file.exists() else None,
                "status": "resumed"
            }

            # Run builder but override tasks
            builder_result = self._run_builder_for_tasks(tasks_to_run)
            results["builder"] = builder_result

            return self.finalize(results)

        except Exception as e:
            return self.handle_error(e, results)

    def run_scout_phase(self) -> Dict:
        """Scout phase: Research architecture and approach."""
        # Load Scout agent config
        scout_config = Path(".foundry/agents/scout.md").read_text()

        # Build prompt based on mode
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Mode-specific instructions
        if self.mode == "new":
            mode_context = "This is a NEW project - you're starting from scratch, no existing codebase."
            job_description = "research and design the architecture for this project"
            focus_areas = """Focus on:
1. Best architecture for this type of project
2. Technology stack and dependencies
3. Project structure and file organization
4. Data models and storage
5. Implementation patterns
6. Potential challenges"""
        elif self.mode == "enhance":
            mode_context = f"This is an EXISTING project at: {self.project_dir}\nYou need to analyze the codebase and plan how to ADD the requested feature."
            job_description = "understand the existing codebase architecture and plan how to integrate the new feature"
            mandatory_steps = """MANDATORY FIRST STEPS - DO NOT SKIP:
1. List ALL files in the project directory (use Glob tool with pattern "**/*")
2. Identify and read the entry point file (index.html for web, main.py for Python, package.json for Node, etc.)
3. Read any files referenced in the entry point (script tags, imports, requires)
4. Document EXACT file paths (e.g., "js/weather-api.js" not "weather-api.js or similar")
5. Identify which SPECIFIC existing files need modification
6. Only suggest creating NEW files if absolutely necessary and no existing file can be modified

DO NOT guess at file names or locations. If you cannot find a file, say so explicitly."""
            focus_areas = """Focus on:
1. Current project structure and patterns (based on actual file listing)
2. Where the new feature fits in the architecture
3. EXACT file paths that need to be created OR modified
4. Integration points with existing code
5. Potential conflicts or breaking changes
6. Testing strategy for the new feature"""
        else:  # fix mode
            mode_context = f"This is an EXISTING project at: {self.project_dir}\nYou need to analyze the codebase and identify how to FIX the reported issue."
            job_description = "understand the existing codebase and identify the root cause of the issue and how to fix it"
            mandatory_steps = """MANDATORY FIRST STEPS - DO NOT SKIP:
1. List ALL files in the project directory (use Glob tool with pattern "**/*")
2. Identify and read the entry point file (index.html for web, main.py for Python, package.json for Node, etc.)
3. Read any files referenced in the entry point (script tags, imports, requires)
4. Document EXACT file paths (e.g., "js/weather-api.js" not "weather-api.js or similar")
5. Identify which SPECIFIC existing files need modification
6. Only suggest creating NEW files if absolutely necessary and no existing file can be modified

DO NOT guess at file names or locations. If you cannot find a file, say so explicitly."""
            focus_areas = """Focus on:
1. Current project structure (based on actual file listing)
2. EXACT files related to the issue (with full paths)
3. Root cause analysis
4. What needs to be fixed in EXISTING files (prefer modification over creation)
5. Potential side effects of the fix
6. Testing strategy to prevent regression"""

        prompt = f"""You are the Scout agent in Context Foundry.

Task: {self.task_description}
Project: {self.project_name}
Project Directory: {self.project_dir}
Current date/time: {current_timestamp}

{mode_context}

Your job is to {job_description}.

{mandatory_steps}

IMPORTANT: You do NOT have file write access. Output your complete response as text.
Do NOT ask for permission to create files. Just provide the full RESEARCH.md content.

{scout_config}

Generate a complete RESEARCH.md following the format in the config.
{focus_areas}

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

        # Add mode-specific file path requirements
        if self.mode in ["fix", "enhance"]:
            file_path_requirements = """
CRITICAL FILE PATH REQUIREMENTS (fix/enhance modes):
- Use EXACT file paths from Scout research (e.g., "js/weather-api.js" not "weather-api.js")
- For each task, explicitly state if it MODIFIES existing file or CREATES new file
- Format: "MODIFY js/config.js" or "CREATE tests/new-feature.test.js"
- DO NOT use vague language like "config.js or similar" or "create/modify"
- If Scout didn't provide exact path, note this as uncertainty requiring investigation
- Prefer MODIFYING existing files over creating new ones
- Validate file paths include directory structure (e.g., "src/", "js/", "lib/")
"""
        else:
            file_path_requirements = ""

        # Build prompt
        prompt = f"""You are the Architect agent in Context Foundry.

Task: {self.task_description}
Project: {self.project_name}
Mode: {self.mode}

Research from Scout phase:
{research_content}
{file_path_requirements}
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

        return self._run_builder_for_tasks(tasks)

    def _run_builder_for_tasks(self, tasks: List[Dict]) -> Dict:
        """Run builder for a specific list of tasks."""
        print(f"Found {len(tasks)} tasks to implement\n")

        # Broadcast phase start
        if self.broadcaster:
            self.broadcaster.phase_change("builder", context_percent=0)
            self.broadcaster.log_line(f"Starting Builder phase: {len(tasks)} tasks")

        completed_tasks = []
        progress_file = self.checkpoints_path / f"PROGRESS_{self.timestamp}.md"
        progress_file.parent.mkdir(parents=True, exist_ok=True)

        # Track file creation across all tasks
        total_impl_files = 0
        total_test_files = 0

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

            # Add mode-specific file instructions
            if self.mode in ["fix", "enhance"]:
                file_instructions = f"""
FILE MODIFICATION RULES (fix/enhance mode):
- This is an EXISTING project at: {self.project_dir}
- Before outputting ANY file, first use Glob or Read to check if it already exists
- If file exists, READ it first, then output the MODIFIED version with your changes
- DO NOT create new files at root level if similar files exist in subdirectories
- Respect the existing directory structure (e.g., if code is in js/, put your code there too)
- File paths from task are EXACT - use them as-is (e.g., "js/config.js" means {self.project_dir}/js/config.js)
- If creating a truly new file, ensure the directory structure matches the project convention
"""
            else:
                file_instructions = ""

            # Build task prompt
            task_prompt = f"""You are the Builder agent implementing Task {i} of {len(tasks)}.

Task: {task['name']}
Description: {task.get('description', '')}
Files: {', '.join(task.get('files', []))}

Project: {self.project_name}
Project directory: {self.project_dir}
Mode: {self.mode}
{file_instructions}
CRITICAL INSTRUCTIONS - READ CAREFULLY:
1. You do NOT have file write access or tools
2. Do NOT ask for permission to create files
3. You MUST output ACTUAL IMPLEMENTATION FILES - not just tests!
4. Output COMPLETE file contents in markdown code blocks

REQUIRED OUTPUT:
1. IMPLEMENTATION FILES FIRST - Create the actual CSS, JS, HTML, or other production files
2. Then create test files if appropriate
3. Use proper type hints and docstrings
4. Both implementation AND tests must be in the SAME response

IMPORTANT: If this task requires CSS files, JS components, or other implementation files,
you MUST generate those files. Do NOT generate only test files.

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
            file_stats = self._extract_and_save_code(response, self.project_dir)
            total_impl_files += file_stats['implementation']
            total_test_files += file_stats['test']

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

            # Git commit with appropriate prefix based on mode
            if self._git_available():
                # Use conventional commit prefixes
                commit_prefix = {
                    "fix": "fix:",
                    "enhance": "feat:",
                    "new": "feat:"
                }.get(self.mode, "chore:")

                self._create_git_commit(
                    f"{commit_prefix} Task {i}: {task['name']}\n\nContext: {metadata['context_percentage']}%"
                )

        # Print summary
        print(f"\n{'='*60}")
        print(f"📊 Builder Phase Summary")
        print(f"{'='*60}")
        print(f"✅ Tasks completed: {len(completed_tasks)}/{len(tasks)}")
        print(f"📁 Implementation files: {total_impl_files}")
        print(f"🧪 Test files: {total_test_files}")
        if total_impl_files == 0:
            print(f"\n⚠️  WARNING: No implementation files were generated!")
            print(f"   This build may be incomplete. Check task outputs.")
        print(f"{'='*60}\n")

        return {
            "tasks_completed": len(completed_tasks),
            "progress_file": str(progress_file),
            "metadata": self.claude.get_context_stats(),
            "files_created": {
                "implementation": total_impl_files,
                "test": total_test_files,
                "total": total_impl_files + total_test_files
            },
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

    def _extract_and_save_code(self, response: str, project_dir: Path) -> dict:
        """Extract code blocks from response and save to files.

        Returns:
            dict with 'total', 'implementation', and 'test' file counts
        """
        import re

        # Try multiple patterns to be flexible
        patterns = [
            # Pattern 1: "File: path" followed by code block
            r"File:\s*([^\n]+)\n```(?:\w+)?\n(.*?)```",
            # Pattern 2: "file: path" (lowercase)
            r"file:\s*([^\n]+)\n```(?:\w+)?\n(.*?)```",
            # Pattern 3: "File path: path"
            r"File path:\s*([^\n]+)\n```(?:\w+)?\n(.*?)```",
            # Pattern 4: "## File: path" (markdown h2 header)
            r"##\s+File:\s*([^\n]+)\n```(?:\w+)?\n(.*?)```",
            # Pattern 5: "### File: path" (markdown h3 header)
            r"###\s+File:\s*([^\n]+)\n```(?:\w+)?\n(.*?)```",
            # Pattern 6: "# File: path" (any markdown header)
            r"#+\s+File:\s*([^\n]+)\n```(?:\w+)?\n(.*?)```",
            # Pattern 7: Just a path in backticks before code block
            r"`([^`\n]+\.[a-z]{2,4})`\n```(?:\w+)?\n(.*?)```",
        ]

        files_created = 0
        test_files = 0
        impl_files = 0

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

                # Strip leading slashes to ensure relative path
                # (Python's Path treats "/file.txt" as absolute, ignoring project_dir)
                filepath = filepath.lstrip('/')

                # Save file
                full_path = (project_dir / filepath).resolve()

                # Security check: ensure file is within project directory
                if not str(full_path).startswith(str(project_dir.resolve())):
                    print(f"   ⚠️  WARNING: Skipping file outside project directory: {filepath}")
                    continue

                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(code)

                print(f"   📁 Created: {full_path}")
                files_created += 1

                # Track test vs implementation files
                if 'test' in filepath.lower() or filepath.startswith('tests/'):
                    test_files += 1
                else:
                    impl_files += 1

        if files_created == 0:
            print(f"   ⚠️  WARNING: No code files were extracted from Builder output!")
            print(f"   💡 Review the task output log file - the LLM may have described files instead of generating code.")
            print(f"   📄 Check: logs/{self.timestamp}/task_*_output.md")
        elif impl_files == 0 and test_files > 0:
            print(f"   ⚠️  WARNING: Only test files were created ({test_files} tests, 0 implementation files)")
            print(f"   💡 The LLM may have misunderstood the task - implementation files are missing!")

        return {'total': files_created, 'implementation': impl_files, 'test': test_files}

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

    def _push_to_github(self) -> bool:
        """Push commits to GitHub remote.

        Returns:
            bool: True if push succeeded, False otherwise
        """
        try:
            # Get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            current_branch = result.stdout.strip()

            # Check if remote exists
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                print(f"\n⚠️  No 'origin' remote configured. Skipping push.")
                print(f"   Configure with: git remote add origin <url>")
                return False

            remote_url = result.stdout.strip()
            print(f"\n📤 Pushing to GitHub...")
            print(f"   Remote: {remote_url}")
            print(f"   Branch: {current_branch}")

            # Push to remote
            result = subprocess.run(
                ["git", "push", "origin", current_branch],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                print(f"✅ Successfully pushed to GitHub!")
                return True
            else:
                print(f"⚠️  Push failed: {result.stderr}")
                if "rejected" in result.stderr.lower():
                    print(f"   💡 Tip: Pull changes first with: git pull origin {current_branch}")
                elif "authentication" in result.stderr.lower() or "permission" in result.stderr.lower():
                    print(f"   💡 Tip: Check your GitHub authentication (SSH key or token)")
                return False

        except subprocess.TimeoutExpired:
            print(f"\n⚠️  Push timed out. Check your network connection.")
            return False
        except Exception as e:
            print(f"\n⚠️  Push failed: {e}")
            return False

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

            # Extract file paths from result dict
            files = [v for k, v in result.items() if k in ('file', 'spec', 'plan', 'tasks') and isinstance(v, str)]
            if files:
                print(f"📄 Files: {', '.join(files)}")

            # Show metadata if available
            if 'metadata' in result:
                meta = result['metadata']
                ctx_pct = meta.get('context_percentage', 0)
                tokens = meta.get('total_tokens', 0)
                print(f"📊 Context: {ctx_pct}% | Tokens: {tokens:,}")

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

        # Display cost summary if using AIClient
        try:
            if hasattr(self.claude, 'get_cost_summary'):
                print(f"\n{self.claude.get_cost_summary(verbose=True)}")
        except Exception:
            # Fallback: calculate approximate cost
            try:
                from ace.pricing_database import PricingDatabase
                db = PricingDatabase()

                # Get provider/model from env
                provider = os.getenv('BUILDER_PROVIDER', 'anthropic')
                model = os.getenv('BUILDER_MODEL', 'claude-sonnet-4-20250514')

                pricing = db.get_pricing(provider, model)

                if pricing and stats.get('total_tokens', 0) > 0:
                    # Use exact token counts if available, otherwise estimate
                    input_tokens = stats.get('total_input_tokens')
                    output_tokens = stats.get('total_output_tokens')

                    if input_tokens is None or output_tokens is None:
                        # Fallback: estimate 30% input, 70% output
                        total_tokens = stats['total_tokens']
                        input_tokens = int(total_tokens * 0.3)
                        output_tokens = int(total_tokens * 0.7)
                        cost_label = "ESTIMATED COST (30/70 split)"
                    else:
                        cost_label = "TOTAL COST"

                    input_cost = input_tokens / 1_000_000 * pricing.input_cost_per_1m
                    output_cost = output_tokens / 1_000_000 * pricing.output_cost_per_1m
                    total_cost = input_cost + output_cost

                    print(f"\n💰 {cost_label}")
                    print("━" * 60)
                    print(f"Input:  {input_tokens:,} tokens × ${pricing.input_cost_per_1m}/1M = ${input_cost:.4f}")
                    print(f"Output: {output_tokens:,} tokens × ${pricing.output_cost_per_1m}/1M = ${output_cost:.4f}")
                    print(f"Total: ${total_cost:.2f}")
                    print(f"Model: {provider}/{model}")
                    print("━" * 60)

                db.close()
            except Exception:
                pass

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
            metrics = analyzer.analyze(self.session_id, self.checkpoints_path)

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

        # Push to GitHub if enabled
        push_success = False
        if self.auto_push:
            if self._git_available():
                push_success = self._push_to_github()
            else:
                print(f"\n⚠️  Auto-push enabled but git is not available")

        return {
            "status": "success",
            "session_id": self.session_id,
            "project_dir": str(self.project_dir),
            "pushed_to_github": push_success,
            "results": results
        }


def main():
    """CLI entry point."""
    if len(sys.argv) < 3:
        print("Usage: python autonomous_orchestrator.py <project_name> <task_description> [--autonomous] [--push]")
        print()
        print("Options:")
        print("  --autonomous  Skip human approval prompts")
        print("  --push        Automatically push to GitHub after successful build")
        print()
        print("Examples:")
        print('  python autonomous_orchestrator.py todo-app "Build CLI todo app"')
        print('  python autonomous_orchestrator.py api-server "REST API with auth" --autonomous')
        print('  python autonomous_orchestrator.py web-app "Build web app" --push')
        sys.exit(1)

    project_name = sys.argv[1]
    task_description = " ".join(sys.argv[2:])
    autonomous = "--autonomous" in sys.argv
    auto_push = "--push" in sys.argv

    # Clean flags from task description
    if autonomous:
        task_description = task_description.replace("--autonomous", "").strip()
    if auto_push:
        task_description = task_description.replace("--push", "").strip()

    orchestrator = AutonomousOrchestrator(
        project_name,
        task_description,
        autonomous=autonomous,
        auto_push=auto_push
    )
    result = orchestrator.run()

    exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
