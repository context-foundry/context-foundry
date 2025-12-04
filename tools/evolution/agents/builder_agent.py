from pathlib import Path
from typing import Dict, Any, Optional, Callable, Union
import json
from datetime import datetime

from tools.evolution.framework.agent_base import Agent
from tools.evolution.framework.llm_provider import LLMProvider, LocalClaudeProvider

class BuilderAgent(Agent):
    """
    Builder Agent - Implements the system based on architecture.
    """

    def __init__(self, llm_provider: LLMProvider = None):
        super().__init__("Builder", llm_provider or LocalClaudeProvider())

    def get_system_prompt(self) -> str:
        return "You are an expert software engineer."

    def run(
        self, 
        working_directory: Union[Path, str], 
        instruction: str, 
        context: Optional[Dict[str, Any]] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """Run the builder agent"""
        
        start_time = datetime.now()

        # Load system prompt
        system_prompt = self.get_system_prompt()
        
        # Construct user prompt with context
        user_prompt = f"Instruction: {instruction}\n\n"
        if context:
            user_prompt += f"Context: {json.dumps(context, indent=2)}\n"

        print(f"🔨 Builder Agent constructing...", flush=True)

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
