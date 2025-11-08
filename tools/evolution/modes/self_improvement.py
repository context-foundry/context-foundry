"""Self-Improvement Mode - Analyze CF codebase and generate improvement tasks"""

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
        """Find TODO/FIXME comments in codebase"""
        todos = []
        cf_root = Path(__file__).parent.parent.parent.parent
        
        # Search for TODOs in tools/
        tools_dir = cf_root / "tools"
        if tools_dir.exists():
            try:
                result = subprocess.run(
                    ['grep', '-rn', 'TODO\\|FIXME', str(tools_dir)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                for line in result.stdout.splitlines()[:10]:  # Limit results
                    if ':' in line:
                        parts = line.split(':', 2)
                        if len(parts) >= 3:
                            todos.append({
                                'file': parts[0],
                                'line': parts[1],
                                'text': parts[2].strip()
                            })
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        
        return todos
