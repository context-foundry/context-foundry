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
from rich.console import Console

# Add parent directory to path for imports
FOUNDRY_ROOT = Path(__file__).parent.parent
sys.path.append(str(FOUNDRY_ROOT))

from ace.ai_client import AIClient
from ace.cost_tracker import CostTracker
from ace.pricing_database import PricingDatabase
from ace.blueprint_manager import BlueprintManager
from foundry.patterns.pattern_manager import PatternLibrary
from foundry.patterns.pattern_extractor import PatternExtractor
from ace.pattern_injection import PatternInjector
from tools.analyze_session import SessionAnalyzer
from tools.livestream.broadcaster import EventBroadcaster

# Rich console for styled output
console = Console()


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
        self.blueprints_path = self.project_dir / ".context-foundry"  # Local to project
        self.checkpoints_path = Path("checkpoints/sessions")
        self.logs_path = Path(f"logs/{self.timestamp}")

        # Create directories
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)

        # Initialize blueprint manager
        self.blueprint_manager = BlueprintManager(self.project_dir)

        # Session
        self.session_id = f"{project_name}_{self.timestamp}"

        # Multi-provider AI client (supports any provider via registry)
        # Configured via SCOUT_PROVIDER, ARCHITECT_PROVIDER, BUILDER_PROVIDER env vars
        self.ai_client = AIClient(
            log_dir=self.logs_path,
            session_id=self.session_id,
            cost_tracker=CostTracker()
        )

        # Note: MCP mode (ctx parameter) not yet supported in AIClient
        # TODO: Add MCP support to AIClient if needed
        if ctx is not None:
            print("⚠️  Warning: MCP mode not yet supported with multi-provider AIClient")

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
        scout_config = (FOUNDRY_ROOT / ".foundry/agents/scout.md").read_text()

        # Build prompt based on mode
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Check if this is a foundry-built project
        is_foundry_project = self.blueprint_manager.is_foundry_project()
        existing_context = ""

        if is_foundry_project and self.mode in ["fix", "enhance"]:
            # Load existing blueprints
            research, spec, plan, tasks = self.blueprint_manager.load_canonical_blueprints()

            print("📚 Detected foundry-built project - loading existing context...")
            print(f"   Found: .context-foundry/ directory")

            # Build context from existing blueprints
            existing_context = f"""
========================================
FOUNDRY-BUILT PROJECT - EXISTING CONTEXT
========================================

This project was originally built by Context Foundry. Below is the existing context from the original build.
Your job is to BUILD ON this existing knowledge, not start from scratch.

### ORIGINAL RESEARCH:
{research or "Not found"}

### ORIGINAL SPECIFICATION:
{spec or "Not found"}

### ORIGINAL PLAN:
{plan or "Not found"}

### ORIGINAL TASKS:
{tasks or "Not found"}

========================================
END OF EXISTING CONTEXT
========================================

Now, for the NEW task: {self.task_description}

Your job is to:
1. Understand what was already built (see above)
2. Identify what needs to change for the new task
3. Update the research/plan to reflect the new requirements
4. Build on the existing architecture, don't reinvent it

IMPORTANT: Use the exact file paths and structure from the existing blueprints above.
"""

        # Mode-specific instructions
        if self.mode == "new":
            mode_context = "This is a NEW project - you're starting from scratch, no existing codebase."
            job_description = "research and design the architecture for this project"
            mandatory_steps = ""
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

{existing_context}

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

        # Call Scout phase with configured provider
        self.ai_client.reset_history('scout')
        response = self.ai_client.scout(prompt)

        # Save RESEARCH.md
        research_file = self.blueprints_path / f"specs/RESEARCH_{self.timestamp}.md"
        research_file.parent.mkdir(parents=True, exist_ok=True)
        research_file.write_text(response.content)

        print(f"✅ Research complete")
        print(f"📄 Saved to: {research_file}")
        print(f"📊 Tokens: {response.input_tokens} in, {response.output_tokens} out")

        # Broadcast completion
        if self.broadcaster:
            self.broadcaster.log_line(f"Scout phase complete - {response.total_tokens} tokens")
            self.broadcaster.context_update(
                0,  # Context percentage not tracked per-phase in AIClient
                response.total_tokens
            )

        # Create metadata dict for compatibility
        metadata = {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "model": response.model,
            "provider": self.ai_client.config.scout.provider
        }

        return {
            "file": str(research_file),
            "content": response.content,
            "metadata": metadata,
            "status": "complete",
        }

    def run_architect_phase(self, scout_result: Dict) -> Dict:
        """Architect phase: Create specifications and implementation plan."""
        research_content = scout_result["content"]

        # Load Architect agent config
        architect_config = (FOUNDRY_ROOT / ".foundry/agents/architect.md").read_text()

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

        # Call Architect phase with configured provider
        self.ai_client.reset_history('architect')
        response = self.ai_client.architect(prompt)

        # Parse response to extract three files
        # For now, save the whole response and prompt user to split
        spec_file = self.blueprints_path / f"specs/SPEC_{self.timestamp}.md"
        plan_file = self.blueprints_path / f"plans/PLAN_{self.timestamp}.md"
        tasks_file = self.blueprints_path / f"tasks/TASKS_{self.timestamp}.md"

        # Simple parsing: look for markdown headers
        files = self._parse_architect_response(response.content)

        # Create directories before writing
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        plan_file.parent.mkdir(parents=True, exist_ok=True)
        tasks_file.parent.mkdir(parents=True, exist_ok=True)

        spec_file.write_text(files.get("spec", response.content))
        plan_file.write_text(files.get("plan", response.content))
        tasks_file.write_text(files.get("tasks", response.content))

        print(f"✅ Architecture complete")
        print(f"📄 SPEC: {spec_file}")
        print(f"📄 PLAN: {plan_file}")
        print(f"📄 TASKS: {tasks_file}")
        print(f"📊 Tokens: {response.input_tokens} in, {response.output_tokens} out")

        # Broadcast completion
        if self.broadcaster:
            self.broadcaster.log_line(f"Architect phase complete - {response.total_tokens} tokens")
            self.broadcaster.context_update(
                0,  # Context percentage not tracked per-phase in AIClient
                response.total_tokens
            )

        # Create metadata dict for compatibility
        metadata = {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "model": response.model,
            "provider": self.ai_client.config.architect.provider
        }

        return {
            "spec": str(spec_file),
            "plan": str(plan_file),
            "tasks": str(tasks_file),
            "spec_content": files.get("spec", response),
            "plan_content": files.get("plan", response),
            "tasks_content": files.get("tasks", response),
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

        # Track all files created by previous tasks for context
        previous_files_created = []

        for i, task in enumerate(tasks, 1):
            # Reset builder history for each task to prevent context overflow
            # Each task is self-contained with SPEC/PLAN/TASKS in prompt
            self.ai_client.reset_history('builder')

            print(f"📝 Task {i}/{len(tasks)}: {task['name']}")

            # Broadcast task start
            if self.broadcaster:
                self.broadcaster.log_line(f"Task {i}/{len(tasks)}: {task['name']}")

            # Check usage stats
            stats = self.ai_client.get_usage_stats()
            print(f"   Total Tokens: {stats['total_tokens']:,}")

            # Broadcast context update
            if self.broadcaster:
                # Note: Context percentage not tracked in AIClient
                self.broadcaster.context_update(0, stats['total_tokens'])

            # Note: Context health tracking and emergency stops
            # are not yet implemented in AIClient
            # TODO: Add context window tracking per provider

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

            # Build previous tasks context
            previous_context = ""
            if previous_files_created:
                previous_context = "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                previous_context += "⚠️  PREVIOUS TASKS COMPLETED - IMPORTANT FILE PATHS:\n"
                previous_context += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                for task_num, files in previous_files_created:
                    previous_context += f"Task {task_num} created:\n"
                    for file_path in sorted(files):
                        previous_context += f"  ✓ {file_path}\n"
                previous_context += "\n⚠️  CRITICAL: When referencing files from previous tasks,\n"
                previous_context += "use the EXACT paths shown above! Do NOT change file locations!\n"
                previous_context += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            # Build task prompt
            task_prompt = f"""You are the Builder agent implementing Task {i} of {len(tasks)}.

Task: {task['name']}
Description: {task.get('description', '')}
Files: {', '.join(task.get('files', []))}

Project: {self.project_name}
Project directory: {self.project_dir}
Mode: {self.mode}
{previous_context}{file_instructions}
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
- Provide production-ready code

⚠️  COMPONENT INTEGRATION CHECKLIST (if creating React/UI components):
□ Wire up all component props - check what parent components expect
□ Connect state management (useState, useContext, props, etc.)
□ Pass callbacks for event handling (onClick, onSubmit, onChange, etc.)
□ Transform/format data to match component prop expectations
□ Import and use hooks properly (useEffect dependencies, etc.)
□ Ensure parent components render children with correct props

Example: If creating SearchBar component that expects onSearch prop,
the parent App component MUST:
- Define a handler function (e.g., handleSearch)
- Pass it as <SearchBar onSearch={{handleSearch}} />
- Use the search value in state or API calls

⚠️  API KEY HANDLING (if task mentions API keys):
□ Extract the actual API key value from the task description
□ For static HTML/JS apps (no package.json):
  - Hard-code the key directly: const API_KEY = 'actual_key_from_task';
  - DO NOT use process.env or .env files (they don't work in browsers)
  - DO NOT use placeholders like 'YOUR_API_KEY' or 'REPLACE_ME'
□ For React/Node.js apps (has package.json):
  - Use environment variables: process.env.REACT_APP_API_KEY
  - The .env file will be auto-generated by foundry
□ Always use the REAL key from the task description, not a placeholder

Example - Static HTML:
Task says: "key=c4b27d06b0817cd09f83aa58745fda97"
Correct: const API_KEY = 'c4b27d06b0817cd09f83aa58745fda97';
Wrong: const API_KEY = 'YOUR_API_KEY';  // ❌ NEVER DO THIS

Example - React:
Correct: const API_KEY = process.env.REACT_APP_WEATHER_API_KEY;

⚠️  CREATE REACT APP (CRA) STRUCTURE REQUIREMENTS:
If the task mentions "Create React App", "CRA", "react-scripts", or package.json has "react-scripts":
□ MUST create public/index.html with:
  - <!DOCTYPE html> declaration
  - <div id="root"></div> for React mounting
  - %PUBLIC_URL% placeholders (e.g., <link rel="icon" href="%PUBLIC_URL%/favicon.ico" />)
□ MUST create src/index.js that renders to #root
□ Optional but recommended: public/manifest.json, public/favicon.ico

Minimal public/index.html template:
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%PUBLIC_URL%/favicon.ico" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>React App</title>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
  </body>
</html>
```

⚠️  CRITICAL: react-scripts will FAIL without public/index.html - always create it!

Additional common CRA files to create if needed:
- src/index.css - Global styles imported by src/index.js
- src/App.css - Component styles for App component
- public/manifest.json - PWA manifest (optional)
- public/favicon.ico - Browser icon (optional)

If you import a file (e.g., `import './index.css'`), you MUST create that file!"""

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

            # Call Builder phase with configured provider (supports per-task overrides)
            response = self.ai_client.builder(task_prompt, task_num=i)

            # Save task output
            task_output = self.logs_path / f"task_{i}_output.md"
            task_output.write_text(response.content)

            # Extract and save code files
            file_stats = self._extract_and_save_code(response.content, self.project_dir)
            total_impl_files += file_stats['implementation']
            total_test_files += file_stats['test']

            # Track files created for this task to include in future task prompts
            if file_stats['files_list']:
                previous_files_created.append((i, file_stats['files_list']))

            print(f"   ✅ Task {i} complete")
            print(f"   📄 Output: {task_output}")
            print(f"   📊 Tokens: {response.input_tokens} in, {response.output_tokens} out")

            # Broadcast task completion
            if self.broadcaster:
                # Note: Context percentage not tracked per-task in AIClient
                self.broadcaster.task_complete(task['name'], 0)

            # Update progress
            completed_tasks.append(
                {
                    "task": i,
                    "name": task["name"],
                    "status": "complete",
                    "tokens": response.total_tokens,
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
                    f"{commit_prefix} Task {i}: {task['name']}\n\nTokens: {response.total_tokens}"
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

        # Generate README if build was successful
        readme_path = None
        if total_impl_files > 0 and self.mode == "new":
            print("📝 Generating README.md...")
            readme_path = self._generate_readme(previous_files_created)
            if readme_path:
                print(f"   ✅ README created: {readme_path}")

        # Generate .env file with API keys if applicable
        env_path = None
        if total_impl_files > 0 and self.mode == "new":
            env_path = self._generate_env_file()
            if env_path:
                print(f"   ✅ Environment file created: {env_path}")
                print(f"   💡 Remember to restart your dev server to load new environment variables")

        # Validate build files for broken references
        validation_result = {"issues": [], "warnings": []}
        if total_impl_files > 0:
            print("\n🔍 Validating file references...")
            all_created_files = []
            for task_num, files in previous_files_created:
                all_created_files.extend(files)

            validation_result = self._validate_build_files(all_created_files)

            if validation_result["issues"]:
                print(f"   ⚠️  Found {len(validation_result['issues'])} issue(s):")
                for issue in validation_result["issues"]:
                    print(f"      • {issue}")
            else:
                print(f"   ✅ All file references valid")

            if validation_result["warnings"]:
                print(f"   ⚠️  {len(validation_result['warnings'])} warning(s):")
                for warning in validation_result["warnings"]:
                    print(f"      • {warning}")

        # Validate project structure (CRA, Vite, etc.)
        structure_result = {"issues": [], "warnings": []}
        if total_impl_files > 0:
            print("\n🏗️  Validating project structure...")
            structure_result = self._validate_project_structure()

            if structure_result["issues"]:
                print(f"   ❌ Found {len(structure_result['issues'])} structure issue(s):")
                for issue in structure_result["issues"]:
                    print(f"      • {issue}")
            else:
                print(f"   ✅ Project structure valid")

            if structure_result["warnings"]:
                print(f"   ⚠️  {len(structure_result['warnings'])} structure warning(s):")
                for warning in structure_result["warnings"]:
                    print(f"      • {warning}")

        # Optional smoke test (disabled by default to save time)
        smoke_test_result = {"success": None, "output": "", "errors": []}
        run_smoke_test = os.getenv('FOUNDRY_SMOKE_TEST', 'false').lower() in ('true', '1', 'yes')

        if run_smoke_test and total_impl_files > 0:
            print("\n🧪 Running smoke test...")
            smoke_test_result = self._run_smoke_test()

            if smoke_test_result["success"] is True:
                print(f"   ✅ {smoke_test_result['output']}")
            elif smoke_test_result["success"] is False:
                print(f"   ❌ Build test failed:")
                for error in smoke_test_result["errors"]:
                    print(f"      • {error}")
            else:
                print(f"   ⏭️  {smoke_test_result['output']}")

        return {
            "tasks_completed": len(completed_tasks),
            "progress_file": str(progress_file),
            "metadata": self.ai_client.get_usage_stats(),
            "files_created": {
                "implementation": total_impl_files,
                "test": total_test_files,
                "total": total_impl_files + total_test_files
            },
            "readme_path": str(readme_path) if readme_path else None,
            "validation": validation_result,
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
            dict with 'total', 'implementation', 'test' counts, and 'files_list' with paths
        """
        import re

        # Try multiple patterns to be flexible
        # Fixed: Allow optional whitespace/newline after language identifier
        patterns = [
            # Pattern 1: "File: path" followed by code block
            r"File:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
            # Pattern 2: "file: path" (lowercase)
            r"file:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
            # Pattern 3: "File path: path"
            r"File path:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
            # Pattern 4: "## File: path" (markdown h2 header)
            r"##\s+File:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
            # Pattern 5: "### File: path" (markdown h3 header)
            r"###\s+File:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
            # Pattern 6: "# File: path" (any markdown header)
            r"#+\s+File:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
            # Pattern 7: Just a path in backticks before code block
            r"`([^`\n]+\.[a-z]{2,4})`\n```(?:\w+)?[ \t]*\n?(.*?)```",
        ]

        files_created = 0
        test_files = 0
        impl_files = 0
        files_list = []  # Track all created file paths

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

                # Fix: Remove duplicate project path prefixes
                # LLM sometimes outputs "examples/weather-app/src/..." when we're already in examples/weather-app/
                if filepath.startswith(f'examples/{self.project_name}/'):
                    filepath = filepath.replace(f'examples/{self.project_name}/', '', 1)
                elif filepath.startswith(f'{self.project_name}/'):
                    filepath = filepath.replace(f'{self.project_name}/', '', 1)

                # Save file
                full_path = (project_dir / filepath).resolve()

                # Security check: ensure file is within project directory
                if not str(full_path).startswith(str(project_dir.resolve())):
                    print(f"   ⚠️  WARNING: Skipping file outside project directory: {filepath}")
                    continue

                full_path.parent.mkdir(parents=True, exist_ok=True)

                # Post-process CRA template variables before writing
                if '%PUBLIC_URL%' in code or '%REACT_APP_' in code:
                    # Replace CRA template variables
                    code = code.replace('%PUBLIC_URL%', '')  # Empty string for local dev
                    # Replace environment variables if available
                    import re
                    env_vars = re.findall(r'%REACT_APP_([A-Z_]+)%', code)
                    for var_name in env_vars:
                        env_value = os.getenv(f'REACT_APP_{var_name}', '')
                        code = code.replace(f'%REACT_APP_{var_name}%', env_value)

                full_path.write_text(code)

                print(f"   📁 Created: {full_path}")
                files_created += 1
                files_list.append(filepath)  # Track the relative path

                # Track test vs implementation files
                if 'test' in filepath.lower() or filepath.startswith('tests/'):
                    test_files += 1
                else:
                    impl_files += 1

        # Enhanced validation: Detect extraction failures
        if files_created == 0:
            # Check if code blocks exist in response
            import re
            code_blocks_found = len(re.findall(r'```\w+', response))
            file_markers_found = len(re.findall(r'(?:File|file):\s*\S+', response))

            print(f"   ⚠️  WARNING: No code files were extracted from Builder output!")

            if code_blocks_found > 0 or file_markers_found > 0:
                print(f"   🔍 Debug: Found {code_blocks_found} code blocks and {file_markers_found} file markers")
                print(f"   ⚠️  This may indicate a regex extraction failure!")
                print(f"   💡 Check the output format - language identifier may not have newline")
            else:
                print(f"   💡 The LLM may have described files instead of generating code.")

            print(f"   📄 Check: logs/{self.timestamp}/task_*_output.md")

        elif impl_files == 0 and test_files > 0:
            print(f"   ⚠️  WARNING: Only test files were created ({test_files} tests, 0 implementation files)")
            print(f"   💡 The LLM may have misunderstood the task - implementation files are missing!")

        return {
            'total': files_created,
            'implementation': impl_files,
            'test': test_files,
            'files_list': files_list
        }

    def _update_progress(
        self, progress_file: Path, completed: List[Dict], total: List[Dict]
    ):
        """Update progress tracking file."""
        stats = self.ai_client.get_usage_stats()

        content = f"""# Build Progress: {self.project_name}
Session: {self.session_id}
Total Tokens: {stats['total_tokens']:,}

## Completed Tasks
"""
        for task in completed:
            content += f"- [x] Task {task['task']}: {task['name']} (Tokens: {task['tokens']:,})\n"

        content += "\n## Remaining Tasks\n"
        for i, task in enumerate(total[len(completed) :], len(completed) + 1):
            content += f"- [ ] Task {i}: {task['name']}\n"

        progress_file.write_text(content)

    def _generate_readme(self, files_created: List) -> Optional[Path]:
        """Generate README.md with project info and run instructions.

        Args:
            files_created: List of (task_num, files_list) tuples

        Returns:
            Path to README.md if created, None otherwise
        """
        # Collect all files (use set to deduplicate)
        all_files_set = set()
        for task_num, files_list in files_created:
            all_files_set.update(files_list)

        if not all_files_set:
            return None

        # Convert to sorted list for consistent ordering
        all_files = sorted(all_files_set)

        # Detect project type
        has_package_json = (self.project_dir / "package.json").exists()
        has_requirements_txt = (self.project_dir / "requirements.txt").exists()
        has_index_html = any('index.html' in f for f in all_files)

        # Determine run instructions
        if has_package_json:
            # Check which npm script to use
            try:
                import json
                package_data = json.loads((self.project_dir / "package.json").read_text())
                scripts = package_data.get('scripts', {})

                # Prefer 'start' for CRA, fall back to 'dev' for Vite/Next
                if 'start' in scripts:
                    npm_command = "npm start"
                elif 'dev' in scripts:
                    npm_command = "npm run dev"
                else:
                    npm_command = "npm start"  # default

                project_type = "Node.js"
            except:
                npm_command = "npm start"  # fallback
                project_type = "Node.js"

            run_instructions = f"""## Quick Start

1. Install dependencies:
   ```bash
   npm install
   ```

2. Run the development server:
   ```bash
   {npm_command}
   ```

3. Open your browser to the URL shown in the terminal (usually http://localhost:3000)"""

        elif has_index_html and not has_package_json:
            project_type = "Static HTML"

            # Check if app makes API calls (likely needs local server for CORS)
            has_api_calls = any('api' in f.lower() or 'fetch' in str(all_files).lower() for f in all_files)

            if has_api_calls:
                run_instructions = """## Quick Start

⚠️  **Important**: This app makes API calls and MUST be run through a local server (not by opening the file directly).

**Option 1 - Python (simplest)**:
```bash
python3 -m http.server 8000
```
Then open http://localhost:8000

**Option 2 - Node.js**:
```bash
npx serve .
```

**Option 3 - VS Code**:
Install "Live Server" extension, then right-click index.html → "Open with Live Server"

**Why?** Opening the HTML file directly (`file:///`) causes CORS errors when making API requests."""
            else:
                run_instructions = """## Quick Start

This is a static HTML/CSS/JavaScript app. No build step needed!

1. Simply open `index.html` in your web browser
2. Or use a local server:
   ```bash
   python3 -m http.server 8000
   ```
   Then open http://localhost:8000"""

        elif has_requirements_txt:
            project_type = "Python"
            main_file = next((f for f in all_files if 'main.py' in f or 'app.py' in f), 'main.py')
            run_instructions = f"""## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python {main_file}
   ```"""

        else:
            project_type = "Application"
            run_instructions = """## Quick Start

See the project files to determine how to run this application."""

        # Extract API keys from task description
        api_key_section = ""
        if 'api' in self.task_description.lower() and 'key' in self.task_description.lower():
            # Try to extract key from description
            import re
            key_match = re.search(r'key[=:\s]+([a-zA-Z0-9]+)', self.task_description, re.IGNORECASE)
            if key_match:
                api_key_section = f"""
## API Configuration

This app uses an API key that's already configured in the code:
- API Key: `{key_match.group(1)}`

To use your own API key, update the relevant configuration file."""

        # Build file structure
        file_structure = "\n".join(f"- `{f}`" for f in sorted(all_files) if not f.startswith('tests/'))

        # Generate README content
        readme_content = f"""# {self.project_name.replace('-', ' ').replace('_', ' ').title()}

{self.task_description}

{run_instructions}{api_key_section}

## Project Structure

{file_structure}

## Built With

- **Type**: {project_type}
- **Generated**: {datetime.now().strftime('%Y-%m-%d')}
- **Tool**: [Context Foundry](https://github.com/your-repo/context-foundry)

---

*This README was automatically generated by Context Foundry*
"""

        # Save README
        readme_path = self.project_dir / "README.md"
        readme_path.write_text(readme_content)

        return readme_path

    def _generate_env_file(self) -> Optional[Path]:
        """Generate .env file with API keys extracted from task description.

        Returns:
            Path to .env if created, None otherwise
        """
        import re

        # Check if task description mentions API keys
        if 'api' not in self.task_description.lower() or 'key' not in self.task_description.lower():
            return None

        # Don't create .env for static HTML apps (they can't use it - no build process)
        package_json_path = self.project_dir / "package.json"
        if not package_json_path.exists():
            # Static HTML app - builder should hard-code keys directly in JS
            return None

        # Extract API key name and value
        # Common patterns:
        # - "key=abc123" or "key: abc123"
        # - "api key abc123" or "API_KEY=abc123"
        # - "openweathermap api key c4b27..."

        env_vars = {}

        # Pattern 1: key=value or key:value
        key_match = re.search(r'key[=:\s]+([a-zA-Z0-9_-]+)', self.task_description, re.IGNORECASE)
        if key_match:
            key_value = key_match.group(1)

            # Detect project type for proper env var naming
            package_json_path = self.project_dir / "package.json"
            if package_json_path.exists():
                try:
                    import json
                    package_data = json.loads(package_json_path.read_text())
                    dependencies = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}

                    # Create React App uses REACT_APP_ prefix
                    if 'react-scripts' in dependencies:
                        env_vars['REACT_APP_WEATHER_API_KEY'] = key_value
                        env_vars['REACT_APP_API_KEY'] = key_value
                    # Vite uses VITE_ prefix
                    elif 'vite' in dependencies:
                        env_vars['VITE_WEATHER_API_KEY'] = key_value
                        env_vars['VITE_API_KEY'] = key_value
                    else:
                        env_vars['API_KEY'] = key_value
                        env_vars['WEATHER_API_KEY'] = key_value
                except:
                    env_vars['API_KEY'] = key_value
            else:
                env_vars['API_KEY'] = key_value

        if not env_vars:
            return None

        # Generate .env content
        env_content = "# Auto-generated by Context Foundry\n"
        env_content += "# API Keys extracted from task description\n\n"
        for key, value in env_vars.items():
            env_content += f"{key}={value}\n"

        # Save .env file
        env_path = self.project_dir / ".env"
        env_path.write_text(env_content)

        return env_path

    def _validate_build_files(self, all_files: List[str]) -> Dict[str, List[str]]:
        """Validate that all file references in the code actually exist.

        Returns:
            dict with 'issues' list and 'warnings' list
        """
        import re

        issues = []
        warnings = []

        # Get all created files as Path objects
        created_files = {Path(f) for f in all_files}
        created_filenames = {p.name for p in created_files}
        created_paths_str = {str(p) for p in created_files}

        # Check HTML files for broken links
        html_files = [f for f in all_files if f.endswith('.html')]
        for html_file in html_files:
            html_path = self.project_dir / html_file
            if not html_path.exists():
                continue

            try:
                content = html_path.read_text()

                # Check CSS links: <link rel="stylesheet" href="...">
                css_links = re.findall(r'<link[^>]*href=["\']([^"\']+\.css)["\']', content)
                for css_link in css_links:
                    # Resolve relative path
                    if not css_link.startswith(('http://', 'https://', '//')):
                        expected_path = (html_path.parent / css_link).resolve()
                        relative_to_project = expected_path.relative_to(self.project_dir)
                        if str(relative_to_project) not in created_paths_str:
                            issues.append(f"{html_file} links to '{css_link}' but file not found at {relative_to_project}")

                # Check JS scripts: <script src="...">
                js_links = re.findall(r'<script[^>]*src=["\']([^"\']+\.js)["\']', content)
                for js_link in js_links:
                    if not js_link.startswith(('http://', 'https://', '//')):
                        expected_path = (html_path.parent / js_link).resolve()
                        relative_to_project = expected_path.relative_to(self.project_dir)
                        if str(relative_to_project) not in created_paths_str:
                            issues.append(f"{html_file} links to '{js_link}' but file not found at {relative_to_project}")

            except Exception as e:
                warnings.append(f"Could not validate {html_file}: {e}")

        # Check JS files for imports
        js_files = [f for f in all_files if f.endswith('.js') and not f.endswith('.test.js')]
        for js_file in js_files:
            js_path = self.project_dir / js_file
            if not js_path.exists():
                continue

            try:
                content = js_path.read_text()

                # Check ES6 imports: import ... from '...'
                imports = re.findall(r'import\s+.*?from\s+["\']([^"\']+)["\']', content)
                for import_path in imports:
                    # Skip node_modules and external packages
                    if not import_path.startswith('.'):
                        continue

                    # Resolve relative import
                    # Only add .js extension if no extension is present
                    _, ext = os.path.splitext(import_path)
                    if not ext:  # No extension, assume .js
                        import_path += '.js'

                    expected_path = (js_path.parent / import_path).resolve()
                    try:
                        relative_to_project = expected_path.relative_to(self.project_dir)
                        if str(relative_to_project) not in created_paths_str:
                            issues.append(f"{js_file} imports '{import_path}' but file not found at {relative_to_project}")
                    except ValueError:
                        # Path is outside project directory, skip
                        pass

                # Check CSS imports: import './styles.css'
                css_imports = re.findall(r'import\s+["\']([^"\']+\.css)["\']', content)
                for css_import in css_imports:
                    # Only check relative imports
                    if css_import.startswith('.'):
                        expected_path = (js_path.parent / css_import).resolve()
                        try:
                            relative_to_project = expected_path.relative_to(self.project_dir)
                            if str(relative_to_project) not in created_paths_str:
                                issues.append(f"{js_file} imports '{css_import}' but file not found at {relative_to_project}")
                        except ValueError:
                            # Path is outside project directory, skip
                            pass

            except Exception as e:
                warnings.append(f"Could not validate {js_file}: {e}")

        return {"issues": issues, "warnings": warnings}

    def _validate_project_structure(self) -> Dict[str, List[str]]:
        """Validate project structure matches detected type (CRA, Vite, etc.).

        Returns:
            dict with 'issues' list and 'warnings' list
        """
        issues = []
        warnings = []

        package_json_path = self.project_dir / "package.json"

        if not package_json_path.exists():
            return {"issues": issues, "warnings": warnings}

        try:
            import json
            package_data = json.loads(package_json_path.read_text())
            dependencies = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}

            # Check for Create React App
            if 'react-scripts' in dependencies:
                # CRA requires specific structure
                public_index = self.project_dir / "public" / "index.html"
                src_index_js = self.project_dir / "src" / "index.js"
                src_index_html = self.project_dir / "src" / "index.html"

                if not public_index.exists():
                    issues.append("Create React App detected but public/index.html is missing (required by react-scripts)")

                if src_index_html.exists():
                    issues.append("Found src/index.html but CRA requires public/index.html - move it to public/ directory")

                if not src_index_js.exists():
                    warnings.append("Create React App detected but src/index.js entry point not found")

            # Check for Vite
            elif 'vite' in dependencies:
                # Vite typically uses index.html in root
                root_index = self.project_dir / "index.html"
                if not root_index.exists():
                    warnings.append("Vite detected but index.html not found in project root")

            # Check for TailwindCSS without config
            if 'tailwindcss' in dependencies:
                tailwind_config = self.project_dir / "tailwind.config.js"
                postcss_config = self.project_dir / "postcss.config.js"

                if not tailwind_config.exists():
                    warnings.append("TailwindCSS installed but tailwind.config.js not found")
                if not postcss_config.exists():
                    warnings.append("TailwindCSS installed but postcss.config.js not found")

        except Exception as e:
            warnings.append(f"Could not validate project structure: {e}")

        return {"issues": issues, "warnings": warnings}

    def _run_smoke_test(self) -> Dict[str, any]:
        """Run optional smoke test to catch build errors.

        Returns:
            dict with 'success' bool, 'output' string, and 'errors' list
        """
        package_json_path = self.project_dir / "package.json"

        if not package_json_path.exists():
            return {"success": None, "output": "No package.json found - skipping smoke test", "errors": []}

        try:
            import json
            package_data = json.loads(package_json_path.read_text())
            scripts = package_data.get('scripts', {})

            # Check if build script exists
            if 'build' not in scripts:
                return {"success": None, "output": "No build script found - skipping smoke test", "errors": []}

            print(f"   Running build test: npm run build")
            print(f"   (This may take a minute...)")

            # Run build with timeout
            result = subprocess.run(
                ['npm', 'run', 'build'],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "output": "Build succeeded",
                    "errors": []
                }
            else:
                # Parse common errors
                errors = []
                stderr = result.stderr

                if "Module not found" in stderr:
                    # Extract module not found errors
                    import re
                    module_errors = re.findall(r"Module not found: Error: Can't resolve '([^']+)'", stderr)
                    for module in module_errors:
                        errors.append(f"Missing module: {module}")

                if "index.html" in stderr and "public" in stderr:
                    errors.append("Missing public/index.html (required for CRA)")

                if not errors:
                    # Just show first few lines of error
                    error_lines = stderr.strip().split('\n')[:5]
                    errors = error_lines

                return {
                    "success": False,
                    "output": result.stderr[:500],  # First 500 chars
                    "errors": errors
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "Build timeout (exceeded 2 minutes)",
                "errors": ["Build took too long - possible infinite loop or large project"]
            }
        except FileNotFoundError:
            return {
                "success": None,
                "output": "npm not found - skipping smoke test",
                "errors": []
            }
        except Exception as e:
            return {
                "success": False,
                "output": str(e),
                "errors": [f"Smoke test failed: {e}"]
            }

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

            console.print("\n[dim]Review the output above. Type 'y' or 'yes' to proceed, or anything else to abort.[/dim]")
            approval = input("\n👉 Proceed with this phase? (y/n): ").strip().lower()

            if approval in ['y', 'yes']:
                return True
            else:
                console.print("\n[yellow]⚠️  Aborted by user.[/yellow]")
                return False

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
        stats = self.ai_client.get_usage_stats()

        print(f"\n{'='*60}")
        print("✅ CONTEXT FOUNDRY WORKFLOW COMPLETE!")
        print(f"{'='*60}")
        print(f"📁 Project: {self.project_dir}")
        print(f"📊 Total Tokens: {stats['total_tokens']:,}")
        print(f"💾 Logs: {self.logs_path}")
        print(f"🎯 Session: {self.session_id}")

        # Display README and run instructions
        builder_result = results.get('builder', {})
        readme_path = builder_result.get('readme_path')
        if readme_path:
            print(f"\n📖 README: {readme_path}")

            # Detect project type and show run instructions
            has_package_json = (self.project_dir / "package.json").exists()
            has_index_html = any((self.project_dir / "index.html").exists() for _ in [1])

            if has_package_json:
                # Detect correct npm command from package.json
                try:
                    import json
                    package_data = json.loads((self.project_dir / "package.json").read_text())
                    scripts = package_data.get('scripts', {})

                    # Prefer 'start' for CRA, fall back to 'dev' for Vite/Next
                    if 'start' in scripts:
                        npm_command = "npm start"
                    elif 'dev' in scripts:
                        npm_command = "npm run dev"
                    else:
                        npm_command = "npm start"  # default
                except:
                    npm_command = "npm start"  # fallback

                print(f"\n🚀 Quick Start:")
                print(f"   cd {self.project_dir}")
                print(f"   npm install")
                print(f"   {npm_command}")
            elif has_index_html:
                print(f"\n🚀 Quick Start:")
                print(f"   Open {self.project_dir}/index.html in your browser")

        # Display cost summary
        try:
            print(f"\n{self.ai_client.get_cost_summary(verbose=True)}")
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

        # Note: Full conversation history not saved with AIClient
        # Individual phase logs are saved by AIClient's log_dir parameter

        # Save session summary
        session_file = self.checkpoints_path / f"{self.session_id}.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(json.dumps(results, indent=2))

        # Save blueprints using BlueprintManager (with history and manifest)
        if all([results.get('scout'), results.get('architect')]):
            try:
                self.blueprint_manager.save_blueprints(
                    research=results['scout']['content'],
                    spec=results['architect'].get('spec_content', ''),
                    plan=results['architect'].get('plan_content', ''),
                    tasks=results['architect'].get('tasks_content', ''),
                    session_id=self.timestamp,
                    mode=self.mode,
                    task_description=self.task_description
                )
                print(f"\n📦 Blueprints saved to: {self.blueprint_manager.context_dir}")
                print(f"   📚 Canonical files updated")
                print(f"   📜 History saved to: history/{self.mode}_{self.timestamp}/")
            except Exception as e:
                print(f"⚠️  Blueprint saving failed: {e}")

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
