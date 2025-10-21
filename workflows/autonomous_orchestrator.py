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
from ace.architects.spec_generator import SpecYamlGenerator, detect_project_type
from ace.architects.contract_test_generator import ContractTestGenerator
from foundry.patterns.pattern_manager import PatternLibrary
from foundry.patterns.pattern_extractor import PatternExtractor
from foundry.validation_cache import ValidationCache
from ace.pattern_injection import PatternInjector
from tools.analyze_session import SessionAnalyzer
from tools.livestream.broadcaster import EventBroadcaster
from workflows.multi_agent_orchestrator import MultiAgentOrchestrator
from ace.validators import BuildValidator, RuntimeValidator, BrowserValidator, StaticValidator, TestRunner
from ace.code_extractor import CodeExtractor
from ace.git_manager import GitManager
from ace.docs_generator import DocsGenerator

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
        use_multi_agent: Optional[bool] = None,  # If None, auto-detect from autonomous flag
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

        # Determine multi-agent mode: use it for autonomous mode unless explicitly disabled
        if use_multi_agent is None:
            use_multi_agent = autonomous and os.getenv('USE_MULTI_AGENT', 'true').lower() in ('true', '1', 'yes')
        self.use_multi_agent = use_multi_agent

        # For fix mode session resume
        self.resume_session = None  # Session ID to resume
        self.resume_tasks = None  # List of task numbers to re-run

        # Paths
        self.project_dir = project_dir or (FOUNDRY_ROOT / "examples" / project_name)
        self.blueprints_path = self.project_dir / ".context-foundry"  # Local to project
        self.checkpoints_path = FOUNDRY_ROOT / "checkpoints" / "sessions"
        self.logs_path = FOUNDRY_ROOT / "logs" / self.timestamp

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

        # Initialize validation cache (enabled by default for faster retries)
        self.validation_cache = ValidationCache(self.project_dir)

        # Initialize validators
        self.build_validator = BuildValidator(self.project_dir)
        self.runtime_validator = RuntimeValidator(self.project_dir)
        self.browser_validator = BrowserValidator(self.project_dir, ai_client=self.ai_client, task_description=task_description)
        self.static_validator = StaticValidator(self.project_dir)
        self.test_runner = TestRunner(self.project_dir, ai_client=self.ai_client, task_description=task_description)

        # Initialize code extractor
        self.code_extractor = CodeExtractor(self.project_dir, project_name=project_name)

        # Initialize git manager
        self.git_manager = GitManager(self.project_dir, project_name=project_name)

        # Initialize docs generator
        self.docs_generator = DocsGenerator(self.project_dir, ai_client=self.ai_client, task_description=task_description, project_name=project_name)

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
        print(f"🚀 Multi-Agent: {'Enabled (parallel)' if self.use_multi_agent else 'Disabled (sequential)'}")
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

            # Use multi-agent orchestration if enabled
            if self.use_multi_agent:
                return self._run_multi_agent()

            # Normal workflow: Scout → Architect → Builder (sequential/legacy mode)
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

    def _run_multi_agent(self) -> Dict:
        """Execute workflow using multi-agent orchestration system.

        Uses parallel Scout and Builder agents for 67% faster execution.
        """
        print("\n🚀 Using Multi-Agent Orchestration (Parallel Mode)")
        print("="*80)

        try:
            # Create multi-agent orchestrator
            orchestrator = MultiAgentOrchestrator(
                project_name=self.project_name,
                task_description=self.task_description,
                project_dir=self.project_dir,
                enable_checkpointing=True,
                enable_self_healing=True,
                max_healing_attempts=3
            )

            # Run multi-agent workflow
            result = orchestrator.run()

            # Convert multi-agent result format to match expected format
            if result.get('success'):
                return {
                    'status': 'success',
                    'project_dir': result.get('project_dir'),
                    'session_id': result.get('session_id'),
                    'results': result.get('results', {}),
                    'metrics': result.get('metrics', {}),
                    'multi_agent': True
                }
            else:
                return {
                    'status': 'error',
                    'error': result.get('error', 'Multi-agent build failed'),
                    'session_id': result.get('session_id'),
                    'multi_agent': True
                }

        except Exception as e:
            print(f"\n❌ Multi-agent execution failed: {e}")
            print("   Falling back to sequential mode...\n")
            # Disable multi-agent and try again with sequential
            self.use_multi_agent = False
            return self.run()

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
            all_tasks = self.code_extractor.parse_tasks(tasks_content)

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
            research, spec, spec_yaml, plan, tasks = self.blueprint_manager.load_canonical_blueprints()

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
            file_path_requirements = """
CRITICAL FILE PATH REQUIREMENTS (new projects):
□ For Create React App / React projects:
  - ALL source files MUST be under src/ directory
  - Components: src/components/*.js (e.g., src/components/Header.js)
  - Services/APIs: src/services/*.js or src/api/*.js (e.g., src/services/weatherService.js)
  - Styles: src/*.css or src/styles/*.css (e.g., src/App.css, src/index.css)
  - Utils/Helpers: src/utils/*.js (e.g., src/utils/formatDate.js)
  - Tests: Co-located with source (e.g., src/components/Header.test.js)
  - Public assets: public/ (e.g., public/index.html, public/favicon.ico)

□ Use FULL paths from project root in task breakdown:
  - ✅ CORRECT: "src/components/WeatherCard.js"
  - ❌ WRONG: "components/WeatherCard.js" or "WeatherCard.js"

□ For other project types (Node.js, Python, etc.):
  - Follow standard conventions for that ecosystem
  - Always specify full paths from project root
"""

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
        files = self.code_extractor.parse_architect_response(response.content)

        # Create directories before writing
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        plan_file.parent.mkdir(parents=True, exist_ok=True)
        tasks_file.parent.mkdir(parents=True, exist_ok=True)

        spec_file.write_text(files.get("spec", response.content))
        plan_file.write_text(files.get("plan", response.content))
        tasks_file.write_text(files.get("tasks", response.content))

        # Phase 2: Generate SPEC.yaml from SPEC.md
        spec_yaml_content = None
        spec_yaml_file = None
        try:
            print("\n🔧 Generating SPEC.yaml...")

            # Detect project type from SPEC.md content
            spec_content = files.get("spec", response.content)
            project_type = detect_project_type(spec_content)
            print(f"   Detected project type: {project_type}")

            # Generate SPEC.yaml
            spec_generator = SpecYamlGenerator(self.ai_client)
            spec_yaml_content = spec_generator.generate(spec_content, project_type)

            # Save SPEC.yaml to .context-foundry directory
            spec_yaml_file = self.blueprints_path / "SPEC.yaml"
            spec_yaml_file.parent.mkdir(parents=True, exist_ok=True)
            spec_yaml_file.write_text(spec_yaml_content)

            print(f"   ✅ SPEC.yaml generated")
            print(f"   📄 Saved to: {spec_yaml_file}")

            # Phase 3: Generate contract tests from SPEC.yaml
            try:
                print("\n🧪 Generating contract tests from SPEC.yaml...")

                test_generator = ContractTestGenerator()
                contract_tests = test_generator.generate_from_yaml(spec_yaml_file)

                # Write contract tests to project directory
                test_files_created = []
                for test_file, test_content in contract_tests.items():
                    test_path = self.project_dir / test_file
                    test_path.parent.mkdir(parents=True, exist_ok=True)
                    test_path.write_text(test_content)
                    test_files_created.append(test_file)
                    print(f"   ✅ Created: {test_file}")

                print(f"   📦 Generated {len(test_files_created)} contract test file(s)")

            except Exception as e:
                print(f"   ⚠️  Contract test generation failed (non-blocking): {e}")
                # Continue without contract tests - this is Phase 3, not critical

        except Exception as e:
            print(f"   ⚠️  SPEC.yaml generation failed (non-blocking): {e}")
            # Continue without SPEC.yaml - this is a Phase 2 feature, not critical

        print(f"\n✅ Architecture complete")
        print(f"📄 SPEC: {spec_file}")
        if spec_yaml_file:
            print(f"📄 SPEC.yaml: {spec_yaml_file}")
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
            "spec_yaml": str(spec_yaml_file) if spec_yaml_file else None,
            "plan": str(plan_file),
            "tasks": str(tasks_file),
            "spec_content": files.get("spec", response),
            "spec_yaml_content": spec_yaml_content,
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
        tasks = self.code_extractor.parse_tasks(tasks_content)

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
□ MUST include "react-scripts" in package.json dependencies:
  ```json
  "dependencies": {{
    "react": "^18.0.0",
    "react-dom": "^18.0.0",
    "react-scripts": "^5.0.0"
  }}
  ```
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
            file_stats = self.code_extractor.extract_and_save_code(response.content, self.project_dir)
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
            if self.git_manager.git_available():
                # Use conventional commit prefixes
                commit_prefix = {
                    "fix": "fix:",
                    "enhance": "feat:",
                    "new": "feat:"
                }.get(self.mode, "chore:")

                self.git_manager.create_git_commit(
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
            readme_path = self.docs_generator.generate_readme(previous_files_created)
            if readme_path:
                print(f"   ✅ README created: {readme_path}")

        # Generate .env file with API keys if applicable
        env_path = None
        if total_impl_files > 0 and self.mode == "new":
            env_path = self.docs_generator.generate_env_file()
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

            validation_result = self.static_validator.validate_build_files(all_created_files)

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
            structure_result = self.static_validator.validate_project_structure()

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

        # ============================================================
        # SELF-HEALING VALIDATION PHASE
        # ============================================================
        run_smoke_test = os.getenv('FOUNDRY_SMOKE_TEST', 'true').lower() in ('true', '1', 'yes')
        validation_failed = False
        failure_reason = None

        if run_smoke_test and total_impl_files > 0:
            print("\n" + "="*60)
            print("🔧 SELF-HEALING VALIDATION PHASE")
            print("="*60)
            print("Running validations with automatic error fixing...")

            # Step 1: Build validation (npm install + npm build) with retry
            print("\n📦 Step 1: Build Validation")
            if not self._retry_until_success(
                validation_fn=self.build_validator.validate,
                context_description="Build validation (npm install + npm build)",
                max_attempts=3,
                cache_key="build"
            ):
                validation_failed = True
                failure_reason = "Build validation failed after 3 attempts"

            # Step 2: Static validation (only if build passed, or no build needed)
            if not validation_failed and validation_result["issues"]:
                print("\n📋 Static Validation Issues Detected:")
                for issue in validation_result["issues"]:
                    print(f"   • {issue}")
                # Don't fail on static validation issues - Builder might have fixed them
                # Just show warnings

            if not validation_failed and structure_result["issues"]:
                print("\n🏗️  Structure Validation Issues Detected:")
                for issue in structure_result["issues"]:
                    print(f"   • {issue}")
                # Don't fail on structure issues - Builder might have fixed them

            # Step 3: Runtime validation (smoke test with retry)
            if not validation_failed:
                print("\n🧪 Step 3: Runtime Validation")
                if not self._retry_until_success(
                    validation_fn=self.runtime_validator.run_smoke_test_wrapper,
                    context_description="Runtime smoke test",
                    max_attempts=3,
                    cache_key="runtime"
                ):
                    validation_failed = True
                    failure_reason = "Runtime validation failed after 3 attempts"

            # Step 4: Browser validation (optional, controlled by env var)
            run_browser_validation = os.getenv('FOUNDRY_BROWSER_VALIDATION', 'true').lower() in ('true', '1', 'yes')
            if not validation_failed and run_browser_validation:
                print("\n🌐 Step 4: Browser Validation (Playwright)")
                if not self._retry_until_success(
                    validation_fn=self.browser_validator.run_browser_validation,
                    context_description="Browser validation (Playwright)",
                    max_attempts=2,
                    cache_key="browser"
                ):
                    validation_failed = True
                    failure_reason = "Browser validation failed after 2 attempts"

        # Check for validation failures
        if validation_failed:
            print("\n" + "="*60)
            print("❌ CONTEXT FOUNDRY WORKFLOW FAILED")
            print("="*60)
            print(f"\nReason: {failure_reason}")
            print(f"Project: {self.project_dir}")
            print("\n⚠️  The build could not complete successfully after multiple attempts.")
            print("Check the error messages above for details.")
            print("\nManual intervention may be required.")
            print("="*60)

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
                "structure": structure_result,
                "status": "failed",
                "failure_reason": failure_reason,
            }

        # SUCCESS!
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
        """Finalize workflow (successful or failed)."""
        stats = self.ai_client.get_usage_stats()

        # Check if build failed
        builder_result = results.get('builder', {})
        build_status = builder_result.get('status', 'complete')
        build_failed = (build_status == 'failed')

        print(f"\n{'='*60}")
        if build_failed:
            print("❌ CONTEXT FOUNDRY WORKFLOW FAILED!")
            failure_reason = builder_result.get('failure_reason', 'Unknown error')
            print(f"{'='*60}")
            print(f"\n⚠️  Build failed: {failure_reason}")
            print(f"📁 Project: {self.project_dir}")
            print(f"\nThe build could not complete successfully.")
            print("Review the error messages above for details.")
        else:
            print("✅ CONTEXT FOUNDRY WORKFLOW COMPLETE!")
            print(f"{'='*60}")
            print(f"📁 Project: {self.project_dir}")

        print(f"📊 Total Tokens: {stats['total_tokens']:,}")
        print(f"💾 Logs: {self.logs_path}")
        print(f"🎯 Session: {self.session_id}")

        # Only show run instructions if build succeeded
        if not build_failed:
            # Display README and run instructions
            readme_path = builder_result.get('readme_path')
            if readme_path:
                print(f"\n📖 README: {readme_path}")

                # Detect project type and show run instructions
                has_package_json = (self.project_dir / "package.json").exists()
                has_index_html = any((self.project_dir / "index.html").exists() for _ in [1])

                if has_package_json:
                    # Detect correct npm command from package.json
                    try:
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
                    task_description=self.task_description,
                    spec_yaml=results['architect'].get('spec_yaml_content')
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
            if self.git_manager.git_available():
                push_success = self.git_manager.push_to_github()
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
