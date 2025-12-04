import argparse
import sys
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.evolution.framework.agent_registry import AgentRegistry

console = Console()

def list_agents(registry: AgentRegistry):
    """List all registered agents."""
    table = Table(title="Context Foundry Agents")
    table.add_column("Agent", style="cyan", no_wrap=True)
    table.add_column("Provider", style="magenta")
    table.add_column("Model / ID", style="green")
    table.add_column("Description", style="dim")

    for name, config in registry.list_agents().items():
        provider = config.get("provider", "unknown")
        if provider == "bedrock-agent":
            details = f"{config.get('agent_id', 'N/A')} ({config.get('alias_id', 'N/A')})"
        else:
            details = config.get("model", "default")
            
        table.add_row(name, provider, details, config.get("description", ""))

    console.print(table)

def switch_agent(registry: AgentRegistry, name: str, provider: str, agent_id: str = None, alias_id: str = None):
    """Switch an agent's provider."""
    try:
        kwargs = {}
        if agent_id:
            kwargs["agent_id"] = agent_id
        if alias_id:
            kwargs["alias_id"] = alias_id
            
        # If switching to local, clear agent_id/alias_id
        if provider == "local":
            kwargs["agent_id"] = None
            kwargs["alias_id"] = None

        registry.update_provider(name, provider, **kwargs)
        console.print(f"[green]Successfully switched agent '{name}' to provider '{provider}'.[/green]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")

def main():
    parser = argparse.ArgumentParser(description="Context Foundry Agent Management")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List command
    subparsers.add_parser("list", help="List all available agents")

    # Switch command
    switch_parser = subparsers.add_parser("switch", help="Switch an agent's provider")
    switch_parser.add_argument("name", help="Name of the agent (e.g., builder)")
    switch_parser.add_argument("provider", choices=["local", "bedrock-agent"], help="Provider type")
    switch_parser.add_argument("--agent-id", help="AWS Bedrock Agent ID (required for bedrock-agent)")
    switch_parser.add_argument("--alias-id", help="AWS Bedrock Alias ID (required for bedrock-agent)")

    args = parser.parse_args()
    
    registry = AgentRegistry()

    if args.command == "list":
        list_agents(registry)
    elif args.command == "switch":
        if args.provider == "bedrock-agent" and not (args.agent_id and args.alias_id):
            console.print("[red]Error: --agent-id and --alias-id are required when switching to bedrock-agent.[/red]")
            sys.exit(1)
        switch_agent(registry, args.name, args.provider, args.agent_id, args.alias_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
