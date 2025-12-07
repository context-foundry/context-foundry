"""Autonomous build and deploy functionality for Context Foundry MCP server.

Handles fully autonomous build/test/fix/deploy workflow with self-healing test loop.
Spawns fresh Claude instances that run in the background with Scout/Architect/Builder/Tester agents.
"""

import json
import os
import subprocess
import sys
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Import BAML integration for type-safe phase tracking
from tools.baml_integration import is_baml_available, get_baml_error

# Import safety mechanisms for sandbox enforcement
from tools.evolution.safety import enforce_sandbox_mode

# Import helper functions from other mcp modules
from tools.mcp_utils.path_utils import get_context_foundry_parent_dir
from tools.mcp_utils.project_detection import detect_existing_codebase
from tools.mcp_utils.task_classification import detect_task_intent
from tools.mcp_utils.delegation import _write_delegation_metadata


def autonomous_build_and_deploy_impl(
    task: str,
    working_directory: str,
    github_repo_name: Optional[str] = None,
    existing_repo: Optional[str] = None,
    mode: str = "new_project",
    enable_test_loop: bool = True,
    max_test_iterations: int = 3,
    timeout_minutes: float = 90.0,
    use_parallel: bool = False,
    incremental: bool = False,
    force_rebuild: bool = False,
    sandbox_path: Optional[str] = None,
    sandbox_task_id: Optional[str] = None,
    active_tasks: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """
    Internal implementation of autonomous_build_and_deploy.

    Fully autonomous build/test/fix/deploy with self-healing test loop.

    **EXECUTION MODE (CURRENT):**
    - Uses orchestrator_prompt.txt with /agents command
    - Inherits Claude Code authentication (no API keys needed)
    - Supports parallel execution via bash process spawning:
      • Phase 2.5: Parallel Builders (2-8 concurrent based on project size)
      • Phase 4.5: Parallel Tests (unit/E2E/lint run simultaneously)
    - **30-45% faster than pure sequential execution**
    - See: docs/PARALLEL_AGENTS_ARCHITECTURE.md

    **OLD PYTHON SYSTEM (DEPRECATED):**
    - use_parallel=True now auto-corrects to False
    - Old system required API keys and external dependencies
    - Removed to eliminate confusion and dependency issues

    Spawns fresh Claude instance that runs in the BACKGROUND:
    - Creates Scout/Architect/Builder/Tester agents
    - Implements complete project autonomously
    - Tests automatically
    - If tests fail: Goes back to Architect → Builder → Test (up to max_test_iterations)
    - If tests pass: Deploys to GitHub
    - Zero human intervention required

    **NON-BLOCKING EXECUTION:**
    - Starts the build immediately
    - Returns task_id right away
    - Build runs in background while you continue working
    - Use get_delegation_result(task_id) to check status
    - Use list_delegations() to see all running builds

    Args:
        task: What to build/fix/enhance
        working_directory: Where to create/work on the project
            - **Relative path** (recommended): Creates project as sibling of context-foundry
              Example: "weather-app" → ~/projects/weather-app
              (if context-foundry is at {CF_ROOT})
            - **Absolute path**: Uses exact path specified
              Example: "/tmp/weather-app" → /tmp/weather-app
            **Core Feature:** Use relative paths to keep all projects organized together!
        github_repo_name: Create new repo (optional)
        existing_repo: Fix/enhance existing (optional)
        mode: "new_project", "fix_bugs", "add_docs"
        enable_test_loop: Enable self-healing test loop (default: True)
        max_test_iterations: Max test/fix cycles (default: 3)
        timeout_minutes: Max execution time (default: 90)
        use_parallel: DEPRECATED - Auto-corrects to False (default: False)
        incremental: Enable incremental builds (default: False, 70-90% faster on rebuilds)
        force_rebuild: Force full rebuild even if incremental enabled (default: False)
        sandbox_path: Sandbox path for Evolution System builds (optional)
        sandbox_task_id: Sandbox task ID for cleanup (optional)
        active_tasks: Dictionary to track active tasks (required from mcp_server.py)

    Returns:
        JSON with task_id and status (returns immediately)

    Examples:
        # Recommended: Use relative path (creates as sibling of context-foundry)
        result = autonomous_build_and_deploy(
            task="Build weather app with OpenWeatherMap API",
            working_directory="weather-app",  # Relative path!
            github_repo_name="weather-app",
            enable_test_loop=True
        )
        # If context-foundry is at {CF_ROOT}
        # This creates: ~/projects/weather-app
        # Returns: {"task_id": "abc-123", "status": "started", ...}

        # Alternative: Use absolute path (if you need specific location)
        result = autonomous_build_and_deploy(
            task="Build temporary test project",
            working_directory="/tmp/test-project",  # Absolute path
            github_repo_name="test-project",
            enable_test_loop=True
        )
        # This creates: /tmp/test-project exactly

        # Continue working while build runs...

        # Check status later
        status = get_delegation_result("abc-123")

        # List all builds
        all_builds = list_delegations()
    """
    try:
        # ═══════════════════════════════════════════════════════════════════════
        # BAML VERIFICATION: Required for type-safe phase tracking
        # ═══════════════════════════════════════════════════════════════════════
        if not is_baml_available():
            error_msg = (
                "❌ BAML is required but not available.\n"
                f"Error: {get_baml_error()}\n\n"
                "BAML is required for type-safe phase tracking in Context Foundry builds.\n"
                "Install with: pip install baml-py\n"
                "Set API key: export OPENAI_API_KEY=your-key\n"
            )
            return json.dumps(
                {
                    "error": error_msg,
                    "baml_available": False,
                    "baml_error": get_baml_error(),
                },
                indent=2,
            )

        print("✅ BAML is available and ready for phase tracking", file=sys.stderr)

        # Determine final working directory FIRST (needed for both modes)
        working_dir_input = Path(working_directory)
        if working_dir_input.is_absolute():
            final_working_dir = working_dir_input
        else:
            cf_parent = get_context_foundry_parent_dir()
            final_working_dir = cf_parent / working_directory

        final_working_dir_str = str(final_working_dir)

        # ═══════════════════════════════════════════════════════════════════════
        # SANDBOX SAFETY: Enforce sandbox-only execution for Evolution System
        # ═══════════════════════════════════════════════════════════════════════
        # Only enforce sandbox mode when sandbox_path is provided (Evolution System builds).
        # Manual builds from Mission Control or CLI are allowed in any directory.
        if sandbox_path:
            try:
                enforce_sandbox_mode(final_working_dir, "autonomous build")
                print(
                    f"✅ Sandbox safety check passed: {final_working_dir}",
                    file=sys.stderr,
                )
            except (PermissionError, RuntimeError) as e:
                # Safety violation - reject the request
                return json.dumps(
                    {
                        "error": str(e),
                        "working_directory": final_working_dir_str,
                        "safety_check": "failed",
                    },
                    indent=2,
                )

        # Validate/create working directory
        if not final_working_dir.exists():
            final_working_dir.mkdir(parents=True, exist_ok=True)

        # Extract project name for display
        project_name = github_repo_name or final_working_dir.name

        # HARD BLOCK: Old Python parallel system is DEPRECATED and REMOVED
        # It required API keys in .env and doesn't inherit Claude Code's auth.
        # Always use the new /agents-based orchestrator instead.
        if use_parallel:
            error_msg = """
❌ ERROR: use_parallel=True is DEPRECATED and DISABLED

The old Python parallel system has been removed because:
  • Required API keys in .env (doesn't inherit Claude Code auth)
  • Had external dependencies (openai package)
  • Superseded by new /agents-based parallel system

The /agents system (use_parallel=False) DOES support parallel execution:
  • Phase 2.5: Parallel Builders (2-8 concurrent agents via bash)
  • Phase 4.5: Parallel Tests (unit/E2E/lint simultaneously)
  • See: docs/PARALLEL_AGENTS_ARCHITECTURE.md

Auto-correcting to use_parallel=False...
"""
            print(error_msg, file=sys.stderr)
            use_parallel = False  # Force correction

        # NEW /agents-based system with orchestrator_prompt.txt
        # This system DOES support parallel execution via bash process spawning:
        # - Phase 2.5: Parallel Builders (2-8 concurrent)
        # - Phase 4.5: Parallel Tests (unit/E2E/lint concurrent)
        print(
            "✅ Using /agents-based orchestrator (supports parallel execution)",
            file=sys.stderr,
        )
        print(
            "   See docs/PARALLEL_AGENTS_ARCHITECTURE.md for details\n", file=sys.stderr
        )

        # ═══════════════════════════════════════════════════════════════════════
        # ENHANCEMENT MODE: Detect existing codebase and task intent
        # ═══════════════════════════════════════════════════════════════════════

        print("🔍 Analyzing workspace...", file=sys.stderr)

        # Detect existing codebase
        codebase_info = detect_existing_codebase(final_working_dir)

        # ═══════════════════════════════════════════════════════════════════
        # FLOWISE KEYWORD DETECTION (for new Flowise projects)
        # ═══════════════════════════════════════════════════════════════════
        # If file-based detection didn't find Flowise flows, check task keywords
        if not codebase_info.get("flowise_flow", False):
            task_lower = task.lower()
            flowise_keywords = [
                "flowise",
                "agent flow",
                "multi-agent flow",
                "chatflow",
                "agentflow",
                "flowise workflow",
            ]

            if any(keyword in task_lower for keyword in flowise_keywords):
                # Activate Flowise extension based on keywords
                print(
                    "🔍 Flowise Extension: Keyword detection triggered!",
                    file=sys.stderr,
                )
                print("   Task contains Flowise keywords", file=sys.stderr)

                codebase_info["flowise_flow"] = True

                # Infer flow type from task description
                if "multi-agent" in task_lower or "multi agent" in task_lower:
                    codebase_info["flowise_flow_type"] = "multi-agent"
                    print("   Inferred flow type: multi-agent", file=sys.stderr)
                elif "rag" in task_lower or "retrieval" in task_lower:
                    codebase_info["flowise_flow_type"] = "rag"
                    print("   Inferred flow type: rag", file=sys.stderr)
                elif "workflow" in task_lower or "orchestrat" in task_lower:
                    codebase_info["flowise_flow_type"] = "workflow"
                    print("   Inferred flow type: workflow", file=sys.stderr)
                elif "chatbot" in task_lower or "chat" in task_lower:
                    codebase_info["flowise_flow_type"] = "chatbot"
                    print("   Inferred flow type: chatbot", file=sys.stderr)
                else:
                    codebase_info["flowise_flow_type"] = "general"
                    print("   Inferred flow type: general", file=sys.stderr)

                # Set default complexity for new projects
                codebase_info["flowise_complexity"] = "moderate"

                # Add flowise to languages if not already there
                if "flowise" not in codebase_info["languages"]:
                    codebase_info["languages"].append("flowise")

                print(
                    "✅ Flowise Extension: Setting flowise_flow=True via keyword detection",
                    file=sys.stderr,
                )

                # Update project type if not already set
                if codebase_info["project_type"] is None:
                    codebase_info["project_type"] = "flowise-workflow"
                    codebase_info["confidence"] = "medium"
        # ═══════════════════════════════════════════════════════════════════

        # Detect task intent from description
        detected_intent = detect_task_intent(task)

        # Log detection results
        if codebase_info["has_code"]:
            print("   ✅ Existing codebase detected:", file=sys.stderr)
            print(f"      Type: {codebase_info['project_type']}", file=sys.stderr)
            print(
                f"      Languages: {', '.join(codebase_info['languages'])}",
                file=sys.stderr,
            )
            print(
                f"      Confidence: {codebase_info['confidence'].upper()}",
                file=sys.stderr,
            )
            if codebase_info["has_git"]:
                git_status = "clean" if codebase_info["git_clean"] else "dirty"
                print(f"      Git: {git_status}", file=sys.stderr)
        else:
            print(
                "   📁 No existing codebase detected (empty/new directory)",
                file=sys.stderr,
            )

        print(
            f"   🎯 Detected intent: {detected_intent.replace('_', ' ').title()}",
            file=sys.stderr,
        )

        # Auto-adjust mode based on detection
        original_mode = mode
        auto_mode = mode  # Start with user-specified mode

        # If user didn't explicitly set mode (left default), use detected intent
        if mode == "new_project" and codebase_info["has_code"]:
            # Existing code detected, use detected intent instead of new_project
            auto_mode = detected_intent
            if detected_intent != "new_project":
                print(
                    f"   🔄 Auto-adjusted mode: new_project → {detected_intent}",
                    file=sys.stderr,
                )

        # Validate mode conflicts
        warnings = []

        if auto_mode == "new_project" and codebase_info["has_code"]:
            warnings.append(
                "⚠️  WARNING: Mode is 'new_project' but existing codebase detected!"
            )
            warnings.append(
                "   Recommendation: Use mode='add_feature' or 'fix_bug' instead"
            )

        if auto_mode != "new_project" and not codebase_info["has_code"]:
            warnings.append(
                f"⚠️  WARNING: Mode is '{auto_mode}' but no existing codebase found!"
            )
            warnings.append("   Recommendation: Use mode='new_project' instead")

        if codebase_info["has_git"] and not codebase_info["git_clean"]:
            warnings.append("⚠️  WARNING: Git repository has uncommitted changes")
            warnings.append(
                "   Recommendation: Commit or stash changes before enhancement"
            )

        # Print warnings
        if warnings:
            print("\n", file=sys.stderr)
            for warning in warnings:
                print(f"   {warning}", file=sys.stderr)
            print("\n", file=sys.stderr)

        # Use auto-adjusted mode
        final_mode = auto_mode

        print(
            f"   ✨ Final mode: {final_mode.replace('_', ' ').title()}\n",
            file=sys.stderr,
        )

        # ═══════════════════════════════════════════════════════════════════════

        # Create orchestrator task configuration with resolved path
        task_config = {
            "task": task,
            "working_directory": final_working_dir_str,
            "github_repo_name": github_repo_name,
            "existing_repo": existing_repo,
            "mode": final_mode,  # Use auto-adjusted mode
            "original_mode": original_mode,  # Keep track of what user requested
            "enable_test_loop": enable_test_loop,
            "max_test_iterations": max_test_iterations,
            # Smart Incremental Builds (Phase 1 implementation)
            "incremental": incremental
            and not force_rebuild,  # Enable only if incremental=True and not forced rebuild
            "force_rebuild": force_rebuild,
            # Flowise extension fields (TOP LEVEL for orchestrator access)
            "flowise_flow": codebase_info.get("flowise_flow", False),
            "flowise_flow_type": codebase_info.get("flowise_flow_type"),
            "flowise_complexity": codebase_info.get("flowise_complexity"),
            "flowise_node_count": codebase_info.get("flowise_node_count", 0),
            "flowise_agent_count": codebase_info.get("flowise_agent_count", 0),
            "flowise_has_memory": codebase_info.get("flowise_has_memory", False),
            "flowise_has_tools": codebase_info.get("flowise_has_tools", False),
            # Enhancement mode: Include codebase detection results
            "codebase_detection": {
                "has_existing_code": codebase_info["has_code"],
                "project_type": codebase_info["project_type"],
                "languages": codebase_info["languages"],
                "confidence": codebase_info["confidence"],
                "has_git": codebase_info["has_git"],
                "git_clean": codebase_info["git_clean"],
                "project_files": codebase_info["project_files"][
                    :10
                ],  # Limit to first 10 files
                "detected_intent": detected_intent,
                # Flowise extension fields (NESTED for backward compatibility)
                "flowise_flow": codebase_info.get("flowise_flow", False),
                "flowise_flow_type": codebase_info.get("flowise_flow_type"),
                "flowise_complexity": codebase_info.get("flowise_complexity"),
                "flowise_node_count": codebase_info.get("flowise_node_count", 0),
                "flowise_agent_count": codebase_info.get("flowise_agent_count", 0),
                "flowise_has_memory": codebase_info.get("flowise_has_memory", False),
                "flowise_has_tools": codebase_info.get("flowise_has_tools", False),
            },
        }

        # Load orchestrator system prompt with caching support
        orchestrator_prompt_path = (
            Path(__file__).parent.parent / "orchestrator_prompt.txt"
        )
        if not orchestrator_prompt_path.exists():
            return json.dumps(
                {
                    "status": "error",
                    "error": f"Orchestrator prompt not found at {orchestrator_prompt_path}. Please create tools/orchestrator_prompt.txt",
                },
                indent=2,
            )

        # Try to use cached prompt builder (with graceful fallback)
        try:
            from tools.prompts.cached_prompt_builder import build_cached_prompt

            # Build prompt with caching enabled
            system_prompt = build_cached_prompt(
                task_config=task_config,
                orchestrator_prompt_path=str(orchestrator_prompt_path),
                enable_caching=True,  # Will auto-disable if not supported
                cache_ttl="5m",
            )

        except Exception as e:
            # Fallback to non-cached prompt if builder fails
            print(f"⚠️  Cached prompt builder failed: {e}", file=sys.stderr)
            print("   Falling back to standard prompt (no caching)\n", file=sys.stderr)

            with open(orchestrator_prompt_path) as f:
                orchestrator_content = f.read()

            # Remove cache boundary marker if present
            orchestrator_content = orchestrator_content.replace(
                "<<CACHE_BOUNDARY_MARKER>>", ""
            )
            orchestrator_content = orchestrator_content.replace(
                "END OF STATIC ORCHESTRATOR INSTRUCTIONS", ""
            )

            # Build task section
            task_section = f"""

AUTONOMOUS BUILD TASK

CONFIGURATION:
{json.dumps(task_config, indent=2)}

Execute the full Scout → Architect → Builder → Test → Deploy workflow.
{"Self-healing test loop is ENABLED. Fix and retry up to " + str(max_test_iterations) + " times if tests fail." if enable_test_loop else "Test loop is DISABLED. Test once and proceed."}

Return JSON summary when complete.
BEGIN AUTONOMOUS EXECUTION NOW.
"""
            system_prompt = orchestrator_content + task_section

        # Build command with thinking disabled
        # Note: System prompt now includes both static (cached) and dynamic (task config) sections
        cmd = [
            "claude",
            "--print",
            "--permission-mode",
            "bypassPermissions",
            "--strict-mcp-config",
            "--settings",
            '{"thinkingMode": "off"}',
            "--system-prompt",
            system_prompt,
            "BEGIN AUTONOMOUS EXECUTION",  # Trigger message for orchestrator
        ]

        # Generate unique task ID
        task_id = str(uuid.uuid4())

        # Prepare environment variables
        process_env = {
            **os.environ,
            "PYTHONUNBUFFERED": "1",
        }

        # Add sandbox mode markers if this is a sandboxed build
        if sandbox_path:
            process_env["CF_SANDBOX_MODE"] = "1"
            process_env["CF_SANDBOX_PATH"] = str(sandbox_path)

        # Start the process (NON-BLOCKING)
        process = subprocess.Popen(
            cmd,
            cwd=final_working_dir_str,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            env=process_env,
        )

        # Store task info in active_tasks (passed from mcp_server.py)
        if active_tasks is not None:
            active_tasks[task_id] = {
                "process": process,
                "cmd": cmd,
                "cwd": final_working_dir_str,
                "task": task,
                "start_time": datetime.now(),
                "timeout_minutes": timeout_minutes,
                "status": "running",
                "result": None,
                "stdout": None,
                "stderr": None,
                "duration": None,
                "task_config": task_config,
                "build_type": "autonomous",  # Mark as autonomous build for special handling
                "sandbox_path": sandbox_path,  # For cleanup when task completes
                "sandbox_task_id": sandbox_task_id,  # For SandboxManager.cleanup_sandbox()
            }

        # Write delegation metadata so DelegationMode can monitor and cleanup
        # CRITICAL: Must include sandbox fields at START so cleanup can work
        _write_delegation_metadata(
            task_id,
            {
                "task_id": task_id,
                "status": "running",
                "task": task,
                "working_directory": final_working_dir_str,
                "start_time": datetime.now().isoformat(),
                "timeout_minutes": timeout_minutes,
                "pid": process.pid,
                "sandbox_path": sandbox_path,  # For cleanup when task completes
                "sandbox_task_id": sandbox_task_id,  # For SandboxManager (legacy, not used)
            },
        )

        return json.dumps(
            {
                "task_id": task_id,
                "status": "started",
                "project": project_name,
                "task_summary": task[:100] + ("..." if len(task) > 100 else ""),
                "working_directory": final_working_dir_str,
                "github_repo": github_repo_name,
                "timeout_minutes": timeout_minutes,
                "enable_test_loop": enable_test_loop,
                "incremental_mode": incremental and not force_rebuild,
                "message": f"""
🚀 Autonomous build started!

Project: {project_name}
Task ID: {task_id}
Location: {final_working_dir_str}
Expected duration: 7-15 minutes
{"⚡ Incremental mode: ENABLED (will reuse cached Scout reports and test results)" if (incremental and not force_rebuild) else ""}

You can continue working - the build runs in the background.

Check status anytime:
  • Ask: "What's the status of task {task_id}?"
  • Or use: get_delegation_result("{task_id}")

List all builds:
  • Ask: "Show all my builds"
  • Or use: list_delegations()

I'll notify you when it's complete!
""".strip(),
            },
            indent=2,
        )

    except Exception as e:
        # Try to use final_working_dir if available, otherwise use original input
        error_working_dir = (
            final_working_dir_str
            if "final_working_dir_str" in locals()
            else working_directory
        )
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "task": task,
                "working_directory": error_working_dir,
            },
            indent=2,
        )
