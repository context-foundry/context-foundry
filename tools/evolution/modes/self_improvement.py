"""Self-Improvement Mode - Analyze CF codebase and generate improvement tasks"""

import re
import subprocess
from pathlib import Path
from typing import List, Dict

from .base_mode import BaseEvolutionMode, TaskResult


class SelfImprovementMode(BaseEvolutionMode):
    """Mode for CF self-improvement through automated analysis"""
    
    def generate_tasks(self) -> List[Dict]:
        """Analyze CF codebase for improvements"""
        tasks = []
        
        # Check for TODOs/FIXMEs
        todos = self._find_todos()
        for todo in todos[:5]:  # Limit to 5 per run
            tasks.append({
                'type': 'self_improvement',
                'params': {
                    'action': 'implement_todo',
                    'file': todo['file'],
                    'line': todo['line'],
                    'description': todo['text']
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
            else:
                prompt = params.get('description', 'Improve Context Foundry')

            # Delegate to Context Foundry via Claude CLI
            print(f"🤖 Delegating to Context Foundry via Claude CLI...")
            result = self._delegate_to_context_foundry(prompt, branch_name)

            if result.get('success'):
                # PERPETUAL LOOP: Queue next improvement task
                print(f"✅ Task completed! Queueing next improvement...")
                self._queue_next_improvement_task()

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
        Find TODO/FIXME comments in codebase

        Searches the entire Context Foundry codebase for TODO and FIXME comments,
        excluding certain directories and files that shouldn't be modified.

        Returns:
            List of dicts with 'file', 'line', and 'text' keys
        """
        todos = []
        cf_root = Path(__file__).parent.parent.parent.parent

        # Directories to search (in priority order)
        search_dirs = [
            cf_root / "tools",
            cf_root / "src",
            cf_root / "tests",
        ]

        # Patterns to exclude from search
        exclude_patterns = [
            '*/venv/*',
            '*/.venv/*',
            '*/node_modules/*',
            '*/__pycache__/*',
            '*.pyc',
            '.git/*',
            '*/dist/*',
            '*/build/*',
        ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            try:
                # Use grep with exclude patterns
                exclude_args = []
                for pattern in exclude_patterns:
                    exclude_args.extend(['--exclude-dir', pattern])

                result = subprocess.run(
                    ['grep', '-rn', '-E', 'TODO|FIXME', str(search_dir)] + exclude_args,
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

                    # Skip self-referential TODOs (this file's section markers)
                    if 'Check for TODOs/FIXMEs' in text:
                        continue

                    # Skip if it's just a comment marker without actual content
                    if text in ['# TODO', '# FIXME', '// TODO', '// FIXME']:
                        continue

                    # Only include lines that have actual TODO/FIXME action items
                    # This filters out false positives like variable names or string contents
                    # Match comment markers followed by TODO or FIXME (with optional colon)
                    # e.g., "# TODO: fix this" or "// FIXME - broken"
                    todo_pattern = r'^[#/\*\-<]+\s*(TODO|FIXME)\s*[:\-]'
                    if not re.search(todo_pattern, text, re.IGNORECASE):
                        continue

                    # Skip TODOs that are part of example code or documentation
                    if 'prompt = f"""Implement TODO' in text or ('File:' in text and 'TODO:' in text):
                        continue

                    todos.append({
                        'file': file_path,
                        'line': line_num,
                        'text': text
                    })

            except subprocess.TimeoutExpired:
                print(f"⚠️  Timeout searching {search_dir}")
            except FileNotFoundError:
                print(f"⚠️  grep command not found, skipping {search_dir}")
            except Exception as e:
                print(f"⚠️  Error searching {search_dir}: {e}")

        # Remove duplicates while preserving order
        seen = set()
        unique_todos = []
        for todo in todos:
            key = (todo['file'], todo['line'])
            if key not in seen:
                seen.add(key)
                unique_todos.append(todo)

        return unique_todos

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
        7. Dashboard detects merge and queues next task
        8. Daemon resumes and picks up next task
        9. PERPETUAL LOOP continues ♾️
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

    def _queue_next_improvement_task(self):
        """
        Generate and queue the NEXT self-improvement task

        This is the PERPETUAL LOOP mechanism that ensures continuous improvement
        """
        try:
            # Find next TODO to implement
            todos = self._find_todos()

            if todos:
                next_todo = todos[0]  # Get first TODO

                # Import here to avoid circular dependency
                from ..task_queue import TaskQueueManager, TaskType

                queue = TaskQueueManager()
                task_id = queue.create_task(
                    task_type=TaskType.SELF_IMPROVEMENT.value,
                    params={
                        'action': 'implement_todo',
                        'file': next_todo['file'],
                        'line': next_todo['line'],
                        'description': next_todo['text']
                    },
                    priority=7
                )

                print(f"✅ PERPETUAL LOOP: Queued next improvement task {task_id}")
                print(f"   📋 Next TODO: {next_todo['text'][:80]}...")

            else:
                print(f"⚠️  No more TODOs found - perpetual loop paused")
                print(f"   Add TODOs/FIXMEs to Context Foundry code to resume")

        except Exception as e:
            print(f"❌ Failed to queue next task: {e}")
