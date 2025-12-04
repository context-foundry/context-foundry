import argparse
import sys
import os
import boto3
import time
from pathlib import Path
from rich.console import Console

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.evolution.framework.agent_registry import AgentRegistry

console = Console()

def get_agent_prompt(agent_name: str) -> str:
    """Read the system prompt for the given agent."""
    # Try cloud-specific prompt first
    cloud_prompt_path = Path(project_root) / "tools" / "prompts" / "phases" / f"phase_{agent_name}_cloud.txt"
    if cloud_prompt_path.exists():
        console.print(f"[blue]Using cloud-optimized prompt for {agent_name}[/blue]")
        return cloud_prompt_path.read_text()
        
    prompt_path = Path(project_root) / "tools" / "prompts" / "phases" / f"phase_{agent_name}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text()

def deploy_stack(agent_name: str, instruction: str):
    """Deploy the CloudFormation stack for the agent."""
    cf_client = boto3.client("cloudformation")
    stack_name = f"ContextFoundry-{agent_name.capitalize()}"
    template_path = Path(project_root) / "infrastructure" / "context_foundry_agent.yaml"
    
    console.print(f"[yellow]Deploying stack {stack_name}...[/yellow]")
    
    try:
        with open(template_path, "r") as f:
            template_body = f.read()
            
        # Check if stack exists
        try:
            cf_client.describe_stacks(StackName=stack_name)
            update = True
        except cf_client.exceptions.ClientError:
            update = False
            
        params = [
            {"ParameterKey": "AgentName", "ParameterValue": f"ContextFoundry-{agent_name.capitalize()}"},
            {"ParameterKey": "Instruction", "ParameterValue": instruction},
            {"ParameterKey": "AgentAliasName", "ParameterValue": "Development"}
        ]
        
        if update:
            console.print("Updating existing stack...")
            cf_client.update_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=params,
                Capabilities=["CAPABILITY_NAMED_IAM"]
            )
        else:
            console.print("Creating new stack...")
            cf_client.create_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=params,
                Capabilities=["CAPABILITY_NAMED_IAM"]
            )
            
        # Wait for completion
        waiter = cf_client.get_waiter("stack_create_complete" if not update else "stack_update_complete")
        waiter.wait(StackName=stack_name)
        
        console.print(f"[green]Stack {stack_name} deployed successfully![/green]")
        
        # Get outputs
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = response["Stacks"][0]["Outputs"]
        
        agent_id = next(o["OutputValue"] for o in outputs if o["OutputKey"] == "AgentId")
        alias_id = next(o["OutputValue"] for o in outputs if o["OutputKey"] == "AgentAliasId")
        
        return agent_id, alias_id
        
    except Exception as e:
        if "No updates are to be performed" in str(e):
            console.print("[green]Stack is already up to date.[/green]")
            # Fetch existing outputs
            response = cf_client.describe_stacks(StackName=stack_name)
            outputs = response["Stacks"][0]["Outputs"]
            agent_id = next(o["OutputValue"] for o in outputs if o["OutputKey"] == "AgentId")
            alias_id = next(o["OutputValue"] for o in outputs if o["OutputKey"] == "AgentAliasId")
            return agent_id, alias_id
        else:
            console.print(f"[red]Deployment failed: {e}[/red]")
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Deploy a Context Foundry agent to AWS Bedrock")
    parser.add_argument("agent", help="Name of the agent (e.g., scout, architect)")
    args = parser.parse_args()
    
    agent_name = args.agent.lower()
    
    try:
        # 1. Get Prompt
        console.print(f"Reading prompt for [cyan]{agent_name}[/cyan]...")
        instruction = get_agent_prompt(agent_name)
        
        # 2. Deploy Stack
        agent_id, alias_id = deploy_stack(agent_name, instruction)
        console.print(f"Agent ID: [bold]{agent_id}[/bold]")
        console.print(f"Alias ID: [bold]{alias_id}[/bold]")
        
        # 3. Update Registry
        console.print("Updating agent registry...")
        registry = AgentRegistry()
        
        # Ensure agent exists in registry
        if agent_name not in registry.list_agents():
            console.print(f"[yellow]Agent '{agent_name}' not found in registry. Creating entry...[/yellow]")
            registry.register_agent(agent_name, {
                "description": f"{agent_name.capitalize()} agent deployed to Bedrock",
                "provider": "bedrock-agent",
                "model": "anthropic.claude-3-5-sonnet-20240620-v1:0"
            })
            
        # Update provider info (but don't force switch unless user wants to)
        # We just store the IDs so they are ready to use
        registry.update_provider(
            agent_name, 
            registry.get_agent(agent_name).get("provider", "local"), # Keep current provider
            agent_id=agent_id,
            alias_id=alias_id
        )
        
        console.print(f"[green]Successfully deployed {agent_name} and updated registry![/green]")
        console.print(f"To start using it, run: [bold]cf agents switch {agent_name} bedrock-agent[/bold]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()
