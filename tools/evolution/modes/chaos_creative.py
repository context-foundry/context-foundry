"""Chaos/Creative Mode - Generate random projects for exploration"""

import random
from typing import List, Dict

from .base_mode import BaseEvolutionMode, TaskResult


class ChaosCreativeMode(BaseEvolutionMode):
    """Mode for creative project generation"""
    
    PROJECT_TYPES = {
        'web_app': 0.30,
        'cli_tool': 0.20,
        'game': 0.15,
        'framework': 0.15,
        'art': 0.10,
        'experiment': 0.10
    }
    
    PROJECT_IDEAS = {
        'web_app': [
            'Real-time collaborative markdown editor',
            'Personal knowledge base with graph visualization',
            'Habit tracker with gamification'
        ],
        'cli_tool': [
            'Git workflow automation tool',
            'Log file analyzer with insights',
            'Development environment setup wizard'
        ],
        'game': [
            'Multiplayer Snake with power-ups',
            'Terminal-based roguelike dungeon crawler',
            'Physics-based puzzle game'
        ],
        'framework': [
            'Lightweight state management library',
            'Testing framework with AI test generation',
            'API mocking framework'
        ],
        'art': [
            'Generative art with procedural algorithms',
            'Music visualizer with WebAudio API',
            'ASCII art generator from images'
        ],
        'experiment': [
            'WebAssembly performance benchmark',
            'Quantum computing simulator',
            'Neural network from scratch'
        ]
    }
    
    def generate_tasks(self) -> List[Dict]:
        """Generate random project idea"""
        project_type = self._weighted_random(self.PROJECT_TYPES)
        project_idea = random.choice(self.PROJECT_IDEAS.get(project_type, ['Generic project']))
        
        return [{
            'type': 'chaos_creative',
            'params': {
                'project_type': project_type,
                'idea': project_idea,
                'tech_stack': self._select_tech_stack(project_type)
            }
        }]
    
    def execute_task(self, task) -> TaskResult:
        """Execute creative project via CF delegation"""
        try:
            params = task.params
            
            # In real implementation, would delegate to CF build system
            # For now, return placeholder result
            
            return TaskResult(
                success=True,
                output={
                    'project_type': params['project_type'],
                    'idea': params['idea'],
                    'tech_stack': params['tech_stack'],
                    'message': 'Project would be built by CF in full implementation'
                }
            )
        except Exception as e:
            return TaskResult(success=False, output=None, error=str(e))
    
    def validate_result(self, result: TaskResult) -> bool:
        """Validate creative project result"""
        return result.success and result.output is not None
    
    def _weighted_random(self, weights: Dict[str, float]) -> str:
        """Select item based on weights"""
        items = list(weights.keys())
        probs = list(weights.values())
        return random.choices(items, weights=probs)[0]
    
    def _select_tech_stack(self, project_type: str) -> List[str]:
        """Select appropriate tech stack"""
        stacks = {
            'web_app': ['react', 'typescript', 'tailwind'],
            'cli_tool': ['python', 'click', 'rich'],
            'game': ['javascript', 'html5-canvas', 'physics-engine'],
            'framework': ['typescript', 'jest', 'rollup'],
            'art': ['javascript', 'p5js', 'webgl'],
            'experiment': ['python', 'numpy', 'jupyter']
        }
        return stacks.get(project_type, ['python'])
