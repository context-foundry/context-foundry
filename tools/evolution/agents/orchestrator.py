import sys
import os
from typing import List, Dict, Any
import json

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.evolution.framework.agent_registry import AgentRegistry
from tools.evolution.framework.llm_provider import LocalClaudeProvider

class Orchestrator:
    """
    The Orchestrator analyzes user requests and selects the appropriate agents.
    """

    def __init__(self):
        self.registry = AgentRegistry()
        # For now, we use LocalClaudeProvider for the orchestration logic itself
        # In the future, this could also be configurable
        self.provider = LocalClaudeProvider()

    def plan_task(self, user_prompt: str) -> List[str]:
        """
        Analyze the prompt and return a list of agent names to execute.
        """
        agents_info = self.registry.list_agents()
        
        system_prompt = f"""
        You are the Orchestrator for Context Foundry.
        Your job is to select the best team of agents to handle a user request.
        
        Available Agents:
        {json.dumps(agents_info, indent=2)}
        
        Rules:
        1. "Research" or "Question" -> ["scout"]
        2. "Plan" or "Design" -> ["scout", "architect"]
        3. "Build" or "Implement" -> ["scout", "architect", "builder", "test"]
        4. "Test" or "Verify" -> ["test"]
        
        Return ONLY a JSON array of agent names in the order they should run.
        Example: ["scout", "architect"]
        """
        
        try:
            response = self.provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            # Parse JSON from response (handle potential markdown blocks)
            clean_response = response.strip()
            if "```json" in clean_response:
                clean_response = clean_response.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_response:
                clean_response = clean_response.split("```")[1].split("```")[0].strip()
                
            plan = json.loads(clean_response)
            return plan
            
        except Exception as e:
            print(f"Orchestration failed: {e}")
            # Fallback to a safe default
            return ["scout"]

    async def execute_task(self, task: str, working_directory: str, github_repo_name: str, model: str = "sonnet") -> Dict[str, Any]:
        """
        Execute a task by planning and running the appropriate agents.
        Returns a task ID and status.
        """
        import uuid
        from datetime import datetime
        from pathlib import Path
        
        task_id = str(uuid.uuid4())
        
        # 1. Plan the task
        plan = self.plan_task(task)
        
        # 2. Create delegation metadata
        delegation_dir = Path.home() / ".context-foundry" / "delegations"
        delegation_dir.mkdir(parents=True, exist_ok=True)
        
        metadata = {
            "task_id": task_id,
            "task": task,
            "working_directory": working_directory,
            "github_repo_name": github_repo_name,
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "plan": plan,
            "current_phase": plan[0] if plan else "unknown",
            "progress_detail": "Starting orchestration..."
        }
        
        (delegation_dir / f"task-{task_id}.json").write_text(json.dumps(metadata, indent=2))
        
        # 3. Start execution in background (simulated for now, or we can actually run it)
        # For the TUI integration, we need to return the task_id immediately.
        # The actual agent execution should happen asynchronously.
        # Since we don't have a full background job system yet, we'll use a simple approach:
        # We will return the task_id, and the TUI will poll.
        # BUT, we need something to actually RUN the agents.
        
        # For this iteration, we will launch a background process to run the agents.
        # We'll create a separate script `run_pipeline.py` that takes the task_id and runs the plan.
        import subprocess
        
        pipeline_script = Path(project_root) / "tools" / "evolution" / "run_pipeline.py"
        if not pipeline_script.exists():
            raise FileNotFoundError(f"Pipeline runner not found at {pipeline_script}")
            
        subprocess.Popen(
            [sys.executable, str(pipeline_script), "--task-id", task_id],
            cwd=project_root,
            stdout=open(delegation_dir / f"task-{task_id}.log", "w"),
            stderr=subprocess.STDOUT
        )
        
        return {
            "task_id": task_id,
            "status": "started",
            "plan": plan
        }


if __name__ == "__main__":
    # Simple test
    orch = Orchestrator()
    print("Plan for 'research auth':", orch.plan_task("research auth"))
    print("Plan for 'build a snake game':", orch.plan_task("build a snake game"))
