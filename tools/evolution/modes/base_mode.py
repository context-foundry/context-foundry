"""Base Evolution Mode - Abstract interface for all modes"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class TaskResult:
    """Result of task execution"""
    success: bool
    output: Any
    error: str = None


class BaseEvolutionMode(ABC):
    """Abstract base class for evolution modes"""
    
    def __init__(self, config: Dict = None):
        """Initialize mode with configuration"""
        self.config = config or {}
    
    @abstractmethod
    def generate_tasks(self) -> List[Dict]:
        """
        Analyze environment and generate improvement tasks
        
        Returns:
            List of task dictionaries with 'type' and 'params'
        """
        pass
    
    @abstractmethod
    def execute_task(self, task) -> TaskResult:
        """
        Execute a single task using CF delegation
        
        Args:
            task: Task object from queue
        
        Returns:
            TaskResult with success status and output
        """
        pass
    
    @abstractmethod
    def validate_result(self, result: TaskResult) -> bool:
        """
        Validate task completion
        
        Args:
            result: TaskResult from execution
        
        Returns:
            True if result is valid and successful
        """
        pass
