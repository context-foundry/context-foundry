"""Self-Improvement Mode - Analyze CF codebase and generate improvement tasks"""

import re
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple

from .base_mode import BaseEvolutionMode, TaskResult


class SelfImprovementMode(BaseEvolutionMode):
    """Mode for CF self-improvement through automated analysis"""

    def generate_tasks(self) -> List[Dict]:
        """Analyze CF codebase for improvements"""
        tasks = []

        # Check for TODOs/FIXMEs with intelligent prioritization
        todos = self._find_todos()

        # Sort TODOs by priority (higher priority first)
        prioritized_todos = sorted(todos, key=lambda t: t.get('priority', 5), reverse=True)

        for todo in prioritized_todos[:5]:  # Limit to 5 highest priority per run
            tasks.append({
                'type': 'self_improvement',
                'params': {
                    'action': 'implement_todo',
                    'file': todo['file'],
                    'line': todo['line'],
                    'description': todo['text'],
                    'priority': todo.get('priority', 5),
                    'category': todo.get('category', 'general')
                }
            })

        return tasks

    def execute_task(self, task) -> TaskResult:
        """
        Execute improvement task via CF delegation

        Creates feature branch and PR for human review
        """
        try:
            params = task.params
            action = params.get('action', '')

            # Create feature branch
            branch_name = f"self-improvement/task-{task.id[:8]}"

            # Build prompt for TODO implementation
            if action == 'implement_todo':
                prompt = f"""Implement TODO found in Context Foundry codebase:

File: {params.get('file', 'N/A')}
Line: {params.get('line', 'N/A')}
TODO: {params.get('description', 'N/A')}

Please:
1. Read the file and understand the context
2. Implement the TODO properly
3. Add tests if needed
4. Ensure all existing tests still pass
5. Create a PR with branch: {branch_name}

This is an autonomous self-improvement task from the Evolution System."""
            elif action == 'self_generated_improvement':
                prompt = params.get('description', 'Improve Context Foundry')
            else:
                prompt = params.get('description', 'Improve Context Foundry')

            # Delegate to Context Foundry via Claude CLI
            print(f"🤖 Delegating to Context Foundry via Claude CLI...")
            result = self._delegate_to_context_foundry(prompt, branch_name)

            if result.get('success'):
                # DO NOT queue next task immediately - wait for daemon to detect PR merge
                # This ensures only 1 PR at a time
                print(f"✅ Task completed! PR will be created by Claude.")
                print(f"⏸️  Waiting for human review before continuing...")

                return TaskResult(
                    success=True,
                    output=result.get('output', {})
                )
            else:
                return TaskResult(
                    success=False,
                    output=None,
                    error=result.get('error', 'Unknown error')
                )

        except Exception as e:
            return TaskResult(success=False, output=None, error=str(e))

    def validate_result(self, result: TaskResult) -> bool:
        """Validate improvement result"""
        return result.success and result.output is not None

    def _find_todos(self) -> List[Dict]:
        """
        Find TODO/FIXME comments in codebase with intelligent prioritization

        Returns:
            List of dicts with 'file', 'line', 'text', 'priority', and 'category' keys
        """
        todos = []
        cf_root = Path(__file__).parent.parent.parent.parent

        # Directories to search (in priority order)
        search_dirs = [
            cf_root / "tools",
            cf_root / "src",
            cf_root / "tests",
        ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            try:
                result = subprocess.run(
                    ['grep', '-rn', 'TODO:\\|FIXME:', str(search_dir)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                for line in result.stdout.splitlines():
                    if ':' not in line:
                        continue

                    parts = line.split(':', 2)
                    if len(parts) < 3:
                        continue

                    file_path = parts[0]
                    line_num = parts[1]
                    text = parts[2].strip()

                    # Only match actual comment TODO: or FIXME: action items
                    # Must start with comment marker (# or //)
                    if not (text.startswith('#') or text.startswith('//')):
                        continue

                    # Must contain TODO: or FIXME: with colon
                    if 'TODO:' not in text and 'FIXME:' not in text:
                        continue

                    # Skip if it's just a comment marker without actual content
                    if text in ['# TODO:', '# FIXME:', '// TODO:', '// FIXME:']:
                        continue

                    # Skip meta-comments about TODOs (not actual action items)
                    skip_patterns = [
                        'Check for TODOs',
                        'intelligent prioritization',
                        'Only match actual TODO',
                        'match actual TODO:',
                        'actual comment TODO:',
                        'Must contain TODO:',
                        'Skip if it',
                        'grep',
                        'Find TODO',
                        'search for TODO',
                        'or FIXME: action',
                        'or FIXME: with'
                    ]
                    if any(pattern in text for pattern in skip_patterns):
                        continue

                    # Calculate priority and category using intelligent analysis
                    priority, category = self._prioritize_todo(text, file_path)

                    todos.append({
                        'file': file_path,
                        'line': line_num,
                        'text': text,
                        'priority': priority,
                        'category': category
                    })

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        # If no TODOs found, generate self-improvement tasks
        if not todos:
            todos = self._generate_improvement_tasks()

        # Remove duplicates while preserving order
        seen = set()
        unique_todos = []
        for todo in todos:
            key = (todo['file'], todo['line'])
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
                'priority': 9,
                'category': 'test_coverage',
                'description': 'Analyze test coverage and add missing tests for critical paths',
                'action': 'self_generated_improvement'
            },
            {
                'priority': 8,
                'category': 'type_safety',
                'description': 'Add type hints to functions missing them for better IDE support',
                'action': 'self_generated_improvement'
            },
            {
                'priority': 7,
                'category': 'error_handling',
                'description': 'Improve error handling and add informative error messages',
                'action': 'self_generated_improvement'
            },
            {
                'priority': 6,
                'category': 'documentation',
                'description': 'Add docstrings to public functions missing documentation',
                'action': 'self_generated_improvement'
            },
            {
                'priority': 5,
                'category': 'code_quality',
                'description': 'Refactor code with high complexity or duplication',
                'action': 'self_generated_improvement'
            },
        ]

        # Return top priority improvement
        if improvement_categories:
            top_improvement = improvement_categories[0]
            improvements.append({
                'file': str(cf_root / "tools"),
                'line': '1',
                'text': top_improvement['description'],
                'priority': top_improvement['priority'],
                'category': top_improvement['category']
            })

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
        category = 'general'

        # FIXME gets higher priority than TODO
        if 'fixme' in text_lower:
            priority += 3
            category = 'bug_fix'

        # Urgency keywords
        urgent_keywords = ['urgent', 'critical', 'asap', 'important', 'bug', 'broken', 'failing']
        if any(keyword in text_lower for keyword in urgent_keywords):
            priority += 2
            if category == 'general':
                category = 'urgent'

        # Security-related TODOs
        security_keywords = ['security', 'vulnerability', 'auth', 'authentication', 'permission', 'xss', 'sanitize', 'sql injection']
        if any(keyword in text_lower for keyword in security_keywords):
            priority += 3
            category = 'security'

        # Performance-related
        perf_keywords = ['performance', 'slow', 'optimize', 'speed', 'bottleneck', 'cache', 'caching']
        if any(keyword in text_lower for keyword in perf_keywords):
            priority += 1
            if category == 'general':
                category = 'performance'

        # Testing-related
        test_keywords = ['test', 'coverage', 'unit test', 'integration test', 'mock']
        if any(keyword in text_lower for keyword in test_keywords):
            priority += 1
            if category == 'general':
                category = 'test'

        # Documentation
        doc_keywords = ['document', 'docs', 'comment', 'docstring']
        if any(keyword in text_lower for keyword in doc_keywords):
            if category == 'general':
                category = 'docs'
            # Documentation is lower priority unless marked urgent
            if 'urgent' not in text_lower:
                priority = max(3, priority - 1)

        # Refactoring
        refactor_keywords = ['refactor', 'cleanup', 'clean up', 'reorganize', 'simplify']
        if any(keyword in text_lower for keyword in refactor_keywords):
            if category == 'general':
                category = 'refactor'

        # Feature (default for general)
        if category == 'general':
            category = 'feature'

        # File path context - core files get higher priority
        if '/core/' in file_path or '/engine/' in file_path:
            priority += 1
        elif '/tests/' in file_path and category != 'test':
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
        Delegate task to Context Foundry via Claude CLI with MCP

        FULLY AUTONOMOUS WORKFLOW:
        1. Daemon spawns claude CLI
        2. Prompts Claude to use MCP autonomous_build_and_deploy
        3. Agents (Scout → Architect → Builder → Test → Deploy) run
        4. PR is created automatically
        5. Dashboard detects PR and pauses daemon
        6. Human reviews and merges PR (HUMAN-IN-THE-LOOP)
        7. Daemon detects PR merge and queues next task
        8. PERPETUAL LOOP continues ♾️

        NOTE: Only 1 task executes at a time to prevent PR flooding
        """
        try:
            import uuid
            import os

            cf_root = Path(__file__).parent.parent.parent.parent
            logs_dir = Path.home() / ".context-foundry" / "evolution" / "delegation-logs"
            logs_dir.mkdir(parents=True, exist_ok=True)

            task_id = str(uuid.uuid4())[:8]
            log_file = logs_dir / f'claude-{task_id}.log'

            # Create the prompt for Claude that tells it to use MCP
            claude_prompt = f"""Execute the following self-improvement task for Context Foundry using the MCP autonomous build system:

TASK:
{prompt}

INSTRUCTIONS:
1. Use the MCP tool: mcp__context-foundry__autonomous_build_and_deploy
2. Parameters:
   - task: (the task description above)
   - working_directory: {cf_root}
   - github_repo_name: context-foundry
   - enable_test_loop: True
   - max_test_iterations: 2

3. The build will run through all phases (Scout, Architect, Builder, Test, Deploy)
4. A PR will be created automatically
5. DO NOT wait for the build to complete - return immediately after spawning it

This is an autonomous self-improvement task. The system will handle PR detection and continuation."""

            # Write prompt to file for debugging
            prompt_file = logs_dir / f'prompt-{task_id}.txt'
            with open(prompt_file, 'w') as f:
                f.write(claude_prompt)

            # Spawn claude CLI in background
            print(f"📝 Spawning Claude CLI (log: {log_file})")
            with open(prompt_file, 'r') as prompt_f:
                process = subprocess.Popen(
                    [
                        '/opt/homebrew/bin/claude',
                        '--print',  # Non-interactive mode
                        '--dangerously-skip-permissions',  # Skip permission dialogs
                    ],
                    stdin=prompt_f,
                    stdout=open(log_file, 'w'),
                    stderr=subprocess.STDOUT,
                    cwd=str(cf_root)
                )

            print(f"✅ Claude CLI spawned (PID: {process.pid})")

            return {
                'success': True,
                'output': {
                    'task_id': task_id,
                    'branch': branch_name,
                    'status': 'claude_spawned',
                    'pid': process.pid,
                    'log_file': str(log_file),
                    'message': f'Claude CLI spawned! (PID: {process.pid})'
                }
            }

        except Exception as e:
            print(f"❌ Failed to spawn Claude CLI: {e}")
            return {
                'success': False,
                'error': f'Failed to spawn Claude CLI: {e}'
            }
