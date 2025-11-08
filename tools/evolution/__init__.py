"""
Context Foundry Evolution System (CFES)
Enables Context Foundry to self-improve, create projects autonomously,
and tackle research problems in perpetual loops.
"""

__version__ = "1.0.0"

from .daemon import EvolutionDaemon
from .task_queue import TaskQueueManager, Task, TaskStatus
from .resource_manager import ResourceManager

__all__ = [
    "EvolutionDaemon",
    "TaskQueueManager",
    "Task",
    "TaskStatus",
    "ResourceManager",
]
