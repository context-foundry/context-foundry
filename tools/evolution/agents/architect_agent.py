from pathlib import Path
from typing import Dict, Any, Optional, Callable, Union
import json
import time
from datetime import datetime

from tools.evolution.framework.agent_base import Agent
from tools.evolution.framework.llm_provider import LLMProvider, LocalClaudeProvider

class ArchitectAgent(Agent):
    """
    Architect Agent - Designs the system architecture.
    """

    def __init__(self, llm_provider: LLMProvider = None):
        super().__init__("Architect", llm_provider or LocalClaudeProvider())

    def get_system_prompt(self) -> str:
        # This should ideally load from tools/prompts/phases/phase_2_architect.md
        # For now, we'll rely on the run method to load it or accept it
        return "You are an expert software architect."

    def run(
        self, 
        working_directory: Union[Path, str], 
        instruction: str, 
        context: Optional[Dict[str, Any]] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """Run the architect agent"""
        
        start_time = datetime.now()

        # Load system prompt
        system_prompt = self.get_system_prompt()
        
        # Construct user prompt with context
        user_prompt = f"Instruction: {instruction}\n\n"
        if context:
            user_prompt += f"Context: {json.dumps(context, indent=2)}\n"

        print(f"🏗️ Architect Agent designing solution...", flush=True)

        try:
            response = self.llm_provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
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
