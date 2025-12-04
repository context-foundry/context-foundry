from pathlib import Path
from typing import Dict, Any, Optional, Callable, Union
from datetime import datetime

from tools.evolution.framework.agent_base import Agent
from tools.evolution.framework.llm_provider import LLMProvider, LocalClaudeProvider

class GenericAgent(Agent):
    """
    Generic Agent - Handles phases that don't require specialized logic.
    Used for Test, Screenshot, Documentation, Deploy, Feedback.
    """

    def __init__(self, name: str, prompt_path: Path = None, llm_provider: LLMProvider = None):
        super().__init__(name, llm_provider or LocalClaudeProvider())
        self.prompt_path = prompt_path

    def get_system_prompt(self) -> str:
        if self.prompt_path and self.prompt_path.exists():
            return self.prompt_path.read_text()
        return f"You are an expert AI assistant specializing in the {self.name} phase."

    def run(
        self, 
        working_directory: Union[Path, str], 
        instruction: str, 
        context: Optional[Dict[str, Any]] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Run the generic phase.
        """
        start_time = datetime.now()
        
        # Determine system prompt
        system_prompt = self.get_system_prompt()
        # Allow override from context
        if context and "system_prompt" in context:
            system_prompt = context["system_prompt"]

        print(f"⏳ {self.name} Agent running...", flush=True)

        try:
            # Execute via LLM Provider
            response = self.llm_provider.generate(
                system_prompt=system_prompt,
                user_prompt=instruction,
                working_directory=working_directory,
                event_callback=event_callback
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return {
                "status": "completed",
                "duration_seconds": duration,
                "output": response
            }

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return {
                "status": "failed",
                "duration_seconds": duration,
                "error": str(e)
            }
