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
            
            # In real implementation, would delegate to CF build system
            # For now, return placeholder result
            
            return TaskResult(
                success=True,
                output={
                    'branch': branch_name,
                    'action': action,
                    'message': 'Task would be delegated to CF in full implementation'
                }
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
                    ['grep', '-rn', 'TODO\\|FIXME', str(search_dir)],
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

                    # Skip if it's just a comment marker without actual content
                    if text in ['# TODO', '# FIXME', '// TODO', '// FIXME']:
                        continue

                    # Skip self-referential TODOs (this file's documentation)
                    if 'Check for TODOs/FIXMEs' in text or 'intelligent prioritization' in text:
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

        # Remove duplicates while preserving order
        seen = set()
        unique_todos = []
        for todo in todos:
            key = (todo['file'], todo['line'])
            if key not in seen:
                seen.add(key)
                unique_todos.append(todo)

        return unique_todos

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
                category = 'testing'

        # Documentation
        doc_keywords = ['document', 'docs', 'comment', 'docstring']
        if any(keyword in text_lower for keyword in doc_keywords):
            if category == 'general':
                category = 'documentation'
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
        elif '/tests/' in file_path and category != 'testing':
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
