from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Union
from .llm_provider import LLMProvider

class Agent(ABC):
    """Abstract base class for Context Foundry Agents."""

    def __init__(self, name: str, llm_provider: LLMProvider):
        self.name = name
        self.llm_provider = llm_provider

    @abstractmethod
    def run(
        self, 
        working_directory: Union[Path, str], 
        instruction: str, 
        context: Optional[Dict[str, Any]] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Any:
        """
        Run the agent's main logic.

        Args:
            working_directory: The project root directory.
            instruction: The specific instruction for this run.
            context: Optional dictionary of context (e.g., previous phase outputs).
            event_callback: Optional callback function to send events during execution.

        Returns:
            The result of the agent's execution.
        """
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass
