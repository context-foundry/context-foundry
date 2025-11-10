"""Self-Improvement Mode - Analyze CF codebase and generate improvement tasks"""

import subprocess
from pathlib import Path
from typing import List, Dict, Tuple

from .base_mode import BaseEvolutionMode, TaskResult
from ..mcp_support import get_mcp_capabilities
from ..sandboxes import SandboxManager
from ..safety import enforce_sandbox_mode, set_sandbox_mode


class SelfImprovementMode(BaseEvolutionMode):
    """Mode for CF self-improvement through automated analysis"""

    # Protected files that should NOT be auto-modified by the daemon
    # These critical infrastructure files require manual review
    PROTECTED_FILES = [
        "tools/evolution/daemon.py",
        "tools/evolution/modes/self_improvement.py",
        "tools/evolution/task_queue.py",
        "tools/evolution/resource_manager.py",
    ]

    def _mcp_status(self) -> Tuple[bool, str]:
        """Return (available, reason) for MCP dependencies."""
        status = get_mcp_capabilities()
        return status["available"], status.get("reason", "")

    def _is_protected_file(self, file_path: str) -> bool:
        """
        Check if a file is protected from autonomous modification

        Args:
            file_path: Path to the file to check

        Returns:
            True if file is protected, False otherwise
        """
        # Normalize path for comparison
        normalized_path = str(Path(file_path))

        # Check if file matches any protected file pattern
        for protected in self.PROTECTED_FILES:
            if normalized_path.endswith(protected) or protected in normalized_path:
                return True

        return False

    def generate_tasks(self) -> List[Dict]:
        """Analyze CF codebase for improvements"""
        tasks = []

        # Check for TODOs/FIXMEs with intelligent prioritization
        todos = self._find_todos()

        # Sort TODOs by priority (higher priority first)
        prioritized_todos = sorted(
            todos, key=lambda t: t.get("priority", 5), reverse=True
        )

        for todo in prioritized_todos[:5]:  # Limit to 5 highest priority per run
            tasks.append(
                {
                    "type": "self_improvement",
                    "params": {
                        "action": "implement_todo",
                        "file": todo["file"],
                        "line": todo["line"],
                        "description": todo["text"],
                        "priority": todo.get("priority", 5),
                        "category": todo.get("category", "general"),
                    },
                }
            )

        return tasks

    def execute_task(self, task) -> TaskResult:
        """
        Execute improvement task via CF delegation

        Creates feature branch and PR for human review
        """
        try:
            # Store task ID for sandbox creation
            self.current_task_id = task.id

            params = task.params
            action = params.get("action", "")

            available, reason = self._mcp_status()
            if not available:
                return TaskResult(
                    success=False,
                    output=None,
                    error=f"MCP unavailable: {reason or 'missing dependencies'}",
                )

            # Create feature branch
            branch_name = f"self-improvement/task-{task.id[:8]}"

            # Build prompt for TODO implementation
            if action == "implement_github_issue":
                issue_num = params.get("github_issue", "N/A")
                issue_title = params.get("description", "N/A")
                issue_details = params.get("details", "")

                prompt = f"""Implement approved GitHub issue #{issue_num}: {issue_title}

{issue_details}

Please:
1. Understand the requirements from the issue description
2. Implement the feature/fix properly
3. Add tests if needed
4. Ensure all existing tests still pass
5. Create a PR with branch: {branch_name}
6. Link the PR to the issue using "Fixes #{issue_num}" in the PR description

This is an autonomous task from the Evolution System implementing a human-approved GitHub issue."""
            elif action == "implement_todo":
                prompt = f"""Implement TODO found in Context Foundry codebase:

File: {params.get("file", "N/A")}
Line: {params.get("line", "N/A")}
TODO: {params.get("description", "N/A")}

Please:
1. Read the file and understand the context
2. Implement the TODO properly
3. Add tests if needed
4. Ensure all existing tests still pass
5. Create a PR with branch: {branch_name}

This is an autonomous self-improvement task from the Evolution System."""
            elif action == "self_generated_improvement":
                prompt = params.get("description", "Improve Context Foundry")
            else:
                prompt = params.get("description", "Improve Context Foundry")

            # Delegate to Context Foundry via Claude CLI
            print("🤖 Delegating to Context Foundry via Claude CLI...")
            result = self._delegate_to_context_foundry(prompt, branch_name)

            if result.get("success"):
                # DO NOT queue next task immediately - wait for daemon to detect PR merge
                # This ensures only 1 PR at a time
                print("✅ Task completed! PR will be created by Claude.")
                print("⏸️  Waiting for human review before continuing...")

                return TaskResult(success=True, output=result.get("output", {}))
            else:
                return TaskResult(
                    success=False,
                    output=None,
                    error=result.get("error", "Unknown error"),
                )

        except Exception as e:
            return TaskResult(success=False, output=None, error=str(e))

    def validate_result(self, result: TaskResult) -> bool:
        """Validate improvement result"""
        return result.success and result.output is not None

    def _load_search_config(self) -> List[str]:
        """
        Load search directories from config file

        Config file: ~/.context-foundry/evolution/todo_search.json
        Format: {"search_dirs": ["tools/cache", "tools/metrics"]}

        Returns:
            List of directory paths (relative to project root), or empty list for defaults
        """
        try:
            config_path = (
                Path.home() / ".context-foundry" / "evolution" / "todo_search.json"
            )
            if config_path.exists():
                import json

                with open(config_path) as f:
                    config = json.load(f)
                    return config.get("search_dirs", [])
        except Exception:
            pass
        return []

    def _find_todos(self) -> List[Dict]:
        """
        Find TODO/FIXME comments in codebase with intelligent prioritization

        Returns:
            List of dicts with 'file', 'line', 'text', 'priority', and 'category' keys
        """
        todos = []
        cf_root = Path(__file__).parent.parent.parent.parent

        # Directories to search (in priority order)
        # Load from config or use defaults
        config_dirs = self._load_search_config()

        if config_dirs:
            # Use configured directories
            search_dirs = [cf_root / Path(d) for d in config_dirs]
        else:
            # Default: only search specific subdirectories for focused improvements
            search_dirs = [
                cf_root / "tools" / "cache",  # Cache system TODOs
                cf_root / "tools" / "metrics",  # Metrics TODOs
                cf_root / "tools" / "incremental",  # Incremental build TODOs
                # Add more specific directories as needed
            ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            try:
                result = subprocess.run(
                    ["grep", "-rn", "TODO:\\|FIXME:", str(search_dir)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                for line in result.stdout.splitlines():
                    if ":" not in line:
                        continue

                    parts = line.split(":", 2)
                    if len(parts) < 3:
                        continue

                    file_path = parts[0]
                    line_num = parts[1]
                    text = parts[2].strip()

                    # Only match actual comment TODO: or FIXME: action items
                    # Must start with comment marker (# or //)
                    if not (text.startswith("#") or text.startswith("//")):
                        continue

                    # Must contain TODO: or FIXME: with colon
                    if "TODO:" not in text and "FIXME:" not in text:
                        continue

                    # Skip if it's just a comment marker without actual content
                    if text in ["# TODO:", "# FIXME:", "// TODO:", "// FIXME:"]:
                        continue

                    # Skip meta-comments about TODOs (not actual action items)
                    skip_patterns = [
                        "Check for TODOs",
                        "intelligent prioritization",
                        "Only match actual TODO",
                        "match actual TODO:",
                        "actual comment TODO:",
                        "Must contain TODO:",
                        "Skip if it",
                        "grep",
                        "Find TODO",
                        "search for TODO",
                        "or FIXME: action",
                        "or FIXME: with",
                    ]
                    if any(pattern in text for pattern in skip_patterns):
                        continue

                    # Skip protected files (critical infrastructure that requires manual review)
                    if self._is_protected_file(file_path):
                        print(f"⏭️  Skipping TODO in protected file: {file_path}")
                        print("   Protected files require manual review for changes")
                        continue

                    # Calculate priority and category using intelligent analysis
                    priority, category = self._prioritize_todo(text, file_path)

                    todos.append(
                        {
                            "file": file_path,
                            "line": line_num,
                            "text": text,
                            "priority": priority,
                            "category": category,
                        }
                    )

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        # If no TODOs found, generate self-improvement tasks
        if not todos:
            todos = self._generate_improvement_tasks()

        # Remove duplicates while preserving order
        seen = set()
        unique_todos = []
        for todo in todos:
            key = (todo["file"], todo["line"])
            if key not in seen:
                seen.add(key)
                unique_todos.append(todo)

        return unique_todos

    def _generate_improvement_tasks(self) -> List[Dict]:
        """
        Generate self-improvement tasks when no TODOs exist

        Analyzes codebase to find opportunities for improvement
        """
        improvements = []
        cf_root = Path(__file__).parent.parent.parent.parent

        # Priority-based improvement categories
        improvement_categories = [
            {
                "priority": 9,
                "category": "test_coverage",
                "description": "Analyze test coverage and add missing tests for critical paths",
                "action": "self_generated_improvement",
            },
            {
                "priority": 8,
                "category": "type_safety",
                "description": "Add type hints to functions missing them for better IDE support",
                "action": "self_generated_improvement",
            },
            {
                "priority": 7,
                "category": "error_handling",
                "description": "Improve error handling and add informative error messages",
                "action": "self_generated_improvement",
            },
            {
                "priority": 6,
                "category": "documentation",
                "description": "Add docstrings to public functions missing documentation",
                "action": "self_generated_improvement",
            },
            {
                "priority": 5,
                "category": "code_quality",
                "description": "Refactor code with high complexity or duplication",
                "action": "self_generated_improvement",
            },
        ]

        # Return top priority improvement
        if improvement_categories:
            top_improvement = improvement_categories[0]
            improvements.append(
                {
                    "file": str(cf_root / "tools"),
                    "line": "1",
                    "text": top_improvement["description"],
                    "priority": top_improvement["priority"],
                    "category": top_improvement["category"],
                }
            )

        return improvements

    def _prioritize_todo(self, text: str, file_path: str) -> Tuple[int, str]:
        """
        Intelligently prioritize TODO/FIXME based on keywords and context

        Args:
            text: The TODO/FIXME comment text
            file_path: Path to the file containing the TODO

        Returns:
            Tuple of (priority, category) where priority is 1-10 (10 highest)
        """
        text_lower = text.lower()
        priority = 5  # Default medium priority
        category = "general"

        # FIXME gets higher priority than TODO
        if "fixme" in text_lower:
            priority += 3
            category = "bug_fix"

        # Urgency keywords
        urgent_keywords = [
            "urgent",
            "critical",
            "asap",
            "important",
            "bug",
            "broken",
            "failing",
        ]
        if any(keyword in text_lower for keyword in urgent_keywords):
            priority += 2
            if category == "general":
                category = "urgent"

        # Security-related TODOs
        security_keywords = [
            "security",
            "vulnerability",
            "auth",
            "authentication",
            "permission",
            "xss",
            "sanitize",
            "sql injection",
        ]
        if any(keyword in text_lower for keyword in security_keywords):
            priority += 3
            category = "security"

        # Performance-related
        perf_keywords = [
            "performance",
            "slow",
            "optimize",
            "speed",
            "bottleneck",
            "cache",
            "caching",
        ]
        if any(keyword in text_lower for keyword in perf_keywords):
            priority += 1
            if category == "general":
                category = "performance"

        # Testing-related
        test_keywords = ["test", "coverage", "unit test", "integration test", "mock"]
        if any(keyword in text_lower for keyword in test_keywords):
            priority += 1
            if category == "general":
                category = "test"

        # Documentation
        doc_keywords = ["document", "docs", "comment", "docstring"]
        if any(keyword in text_lower for keyword in doc_keywords):
            if category == "general":
                category = "docs"
            # Documentation is lower priority unless marked urgent
            if "urgent" not in text_lower:
                priority = max(3, priority - 1)

        # Refactoring
        refactor_keywords = [
            "refactor",
            "cleanup",
            "clean up",
            "reorganize",
            "simplify",
        ]
        if any(keyword in text_lower for keyword in refactor_keywords):
            if category == "general":
                category = "refactor"

        # Feature (default for general)
        if category == "general":
            category = "feature"

        # File path context - core files get higher priority
        if "/core/" in file_path or "/engine/" in file_path:
            priority += 1
        elif "/tests/" in file_path and category != "test":
            priority -= 1

        # Cap priority at 10
        priority = min(10, max(1, priority))

        return priority, category

    def _calculate_todo_priority(self, text: str) -> int:
        """
        Calculate priority score for a TODO (1-10, higher = more urgent)
        Wrapper method that calls _prioritize_todo
        """
        priority, _ = self._prioritize_todo(text, "")
        return priority

    def _categorize_todo(self, text: str) -> str:
        """
        Categorize TODO by type
        Wrapper method that calls _prioritize_todo
        """
        _, category = self._prioritize_todo(text, "")
        return category

    def _delegate_to_context_foundry(self, prompt: str, branch_name: str) -> Dict:
        """
        Delegate task to Context Foundry MCP server directly

        FULLY AUTONOMOUS WORKFLOW:
        1. Daemon calls MCP autonomous_build_and_deploy() directly
        2. MCP spawns Scout → Architect → Builder → Test → Deploy agents
        3. PR is created automatically
        4. Daemon monitors MCP progress via get_delegation_result()
        5. Dashboard shows MCP status in real-time
        6. Human reviews and merges PR (HUMAN-IN-THE-LOOP)
        7. Daemon detects PR merge and queues next task
        8. PERPETUAL LOOP continues ♾️

        NOTE: Only 1 task executes at a time to prevent PR flooding
        """
        try:
            available, reason = self._mcp_status()
            if not available:
                return {
                    "success": False,
                    "error": f"MCP unavailable: {reason or 'missing dependencies'}",
                }

            import json

            # Import MCP server implementation function (not the decorated tool)
            from tools.mcp_server import _autonomous_build_and_deploy_impl

            # Get task ID for sandbox creation
            task_id = getattr(self, "current_task_id", "unknown")

            # 🏗️ CREATE ISOLATED SANDBOX (protects production!)
            print("🏗️  Creating isolated sandbox for autonomous build...")
            manager = SandboxManager()
            sandbox_path = manager.create_sandbox(
                repo_url="https://github.com/context-foundry/context-foundry.git",
                task_id=task_id,
            )

            # Verify sandbox safety
            enforce_sandbox_mode(sandbox_path, "autonomous build")
            set_sandbox_mode(sandbox_path)

            print(f"✅ Sandbox created: {sandbox_path}")
            print("   Production directory protected: ✅")
            print("🤖 Calling Context Foundry MCP autonomous_build_and_deploy()...")
            print(f"   Task: {prompt[:100]}...")
            print(f"   Branch: {branch_name}")

            # Call MCP implementation function directly (non-blocking, returns task_id immediately)
            # NOTE: Sandbox cleanup is deferred to delegation monitor when MCP process completes
            result_json = _autonomous_build_and_deploy_impl(
                task=prompt,
                working_directory=str(sandbox_path),  # ✅ SANDBOX (not production!)
                github_repo_name="context-foundry/context-foundry",
                existing_repo=str(sandbox_path),  # ✅ SANDBOX (not production!)
                mode="existing_repo",
                enable_test_loop=True,
                max_test_iterations=3,
                timeout_minutes=90.0,
                use_parallel=True,
                sandbox_path=str(sandbox_path),  # For cleanup tracking
                sandbox_task_id=task_id,  # For SandboxManager.cleanup_sandbox()
            )

            # Parse MCP result
            result = json.loads(result_json)
            mcp_task_id = result.get("task_id")

            print("✅ MCP task started!")
            print(f"   MCP Task ID: {mcp_task_id}")
            print(f"   Status: {result.get('status')}")
            print(f"   Monitor progress: get_delegation_result('{mcp_task_id}')")

            return {
                "success": True,
                "output": {
                    "mcp_task_id": mcp_task_id,
                    "branch": branch_name,
                    "status": "mcp_running",
                    "message": result.get("message", "MCP autonomous build started"),
                    "working_directory": str(sandbox_path),
                    "sandbox_path": str(sandbox_path),  # For cleanup later
                    "sandbox_task_id": task_id,  # For SandboxManager.cleanup_sandbox()
                },
            }

        except Exception as e:
            print(f"❌ Failed to call MCP autonomous_build_and_deploy: {e}")
            import traceback

            traceback.print_exc()
            return {"success": False, "error": f"Failed to call MCP: {e}"}
