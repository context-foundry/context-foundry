import sys
import os
import json
import argparse
from pathlib import Path
import time
import asyncio

# Add project root
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.evolution.framework.agent_registry import AgentRegistry
from tools.evolution.framework.llm_provider import BedrockAgentProvider, LocalClaudeProvider

async def run_pipeline(task_id: str):
    delegation_dir = Path.home() / ".context-foundry" / "delegations"
    task_file = delegation_dir / f"task-{task_id}.json"
    log_file = delegation_dir / f"task-{task_id}.log"
    
    if not task_file.exists():
        print(f"Task file not found: {task_file}")
        sys.exit(1)
        
    metadata = json.loads(task_file.read_text())
    plan = metadata.get("plan", [])
    task = metadata.get("task")
    working_dir = Path(metadata.get("working_directory"))
    
    # Ensure working directory exists
    working_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Starting pipeline for task: {task}")
    print(f"Plan: {plan}")
    
    registry = AgentRegistry()
    
    for agent_name in plan:
        print(f"\n=== Running Agent: {agent_name} ===")
        
        # Update metadata
        metadata = json.loads(task_file.read_text()) # Reload to avoid overwrites
        metadata["current_phase"] = agent_name
        metadata["progress_detail"] = f"Running {agent_name}..."
        task_file.write_text(json.dumps(metadata, indent=2))
        
        # Get agent config
        agent_config = registry.get_agent(agent_name)
        if not agent_config:
            print(f"Agent {agent_name} not found in registry. Skipping.")
            continue
            
        provider_type = agent_config.get("provider", "local")
        print(f"Provider: {provider_type}")
        
        try:
            if provider_type == "bedrock-agent":
                agent_id = agent_config.get("agent_id")
                alias_id = agent_config.get("alias_id")
                
                if not (agent_id and alias_id):
                    print(f"Missing IDs for Bedrock agent {agent_name}. Falling back to local.")
                    provider = LocalClaudeProvider()
                else:
                    provider = BedrockAgentProvider(
                        agent_id=agent_id,
                        agent_alias_id=alias_id
                    )
            else:
                provider = LocalClaudeProvider()
                
            # Invoke the agent
            # We construct a prompt based on the agent's role
            # For now, we pass the original task + context from previous steps
            # Ideally, we'd pass the previous agent's output.
            
            # Simple context passing: Read report files if they exist
            context = ""
            if (Path.home() / ".context-foundry" / "scout-report.md").exists():
                context += "\n\nScout Report:\n" + (Path.home() / ".context-foundry" / "scout-report.md").read_text()
            if (Path.home() / ".context-foundry" / "implementation_plan.md").exists():
                context += "\n\nImplementation Plan:\n" + (Path.home() / ".context-foundry" / "implementation_plan.md").read_text()
                
            full_prompt = f"Task: {task}\n{context}"
            
            # Run generation
            # Note: BedrockAgentProvider.generate handles the loop
            response = provider.generate(
                system_prompt="", # Bedrock agents have their own system prompt
                user_prompt=full_prompt,
                working_directory=working_directory
            )
            
            print(f"Agent {agent_name} finished.")
            print(f"Response length: {len(response)}")
            
        except Exception as e:
            print(f"Error running agent {agent_name}: {e}")
            metadata["status"] = "failed"
            metadata["progress_detail"] = f"Failed at {agent_name}: {e}"
            task_file.write_text(json.dumps(metadata, indent=2))
            sys.exit(1)
        
    metadata = json.loads(task_file.read_text())
    metadata["status"] = "completed"
    metadata["progress_detail"] = "All agents completed successfully."
    metadata["end_time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    task_file.write_text(json.dumps(metadata, indent=2))
    print("Pipeline completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args()
    
    asyncio.run(run_pipeline(args.task_id))
