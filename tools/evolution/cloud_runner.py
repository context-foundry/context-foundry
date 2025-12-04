"""
Cloud Runner - Entry point for the "Cloud Brain".

This script is designed to run in a cloud environment (e.g., AWS Lambda, Fargate).
It connects to the "Local Hands" (Daemon) via the RemoteToolExecutor.

Model Selection:
    - Use --model to specify a Bedrock model ID
    - Or set CF_PHASE_<AGENT>=bedrock:<model> environment variable
    - Or configure ~/.context-foundry/provider_config.json

Examples:
    # Use default model from config
    python3 cloud_runner.py --agent builder --instruction "Create hello.py"

    # Use specific model
    python3 cloud_runner.py --agent builder --model anthropic.claude-opus-4-5-20251101-v1:0 --instruction "..."

    # Use Qwen for code generation
    python3 cloud_runner.py --agent builder --model qwen.qwen3-coder-480b-v1:0 --instruction "..."
"""

import os
import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tools.evolution.communication.cloud_client import RemoteToolExecutor
from tools.evolution.framework.llm_provider import BedrockProvider
from tools.evolution.framework.provider_config import get_provider_for_phase, print_current_config
from tools.evolution.agents.builder_agent import BuilderAgent
from tools.evolution.agents.architect_agent import ArchitectAgent


def main():
    parser = argparse.ArgumentParser(
        description="Run an agent in the Cloud Brain (AWS Bedrock).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run builder with default model
  %(prog)s --agent builder --instruction "Create a hello world script" --working-directory /path/to/project

  # Run with specific model (Opus 4.5)
  %(prog)s --agent builder --model anthropic.claude-opus-4-5-20251101-v1:0 --instruction "..."

  # Run with Qwen for code tasks
  %(prog)s --agent builder --model qwen.qwen3-coder-480b-v1:0 --instruction "..."

  # Show current provider configuration
  %(prog)s --show-config
        """
    )
    parser.add_argument("--agent", help="Agent to run (architect, builder, scout, or any phase name)")
    parser.add_argument("--instruction", help="Instruction for the agent")
    parser.add_argument("--daemon-url", default="http://localhost:8421", help="URL of the Local Hands daemon")
    parser.add_argument("--working-directory", help="Working directory on the Local Hands machine")
    parser.add_argument("--api-key", help="API Key for the Local Hands daemon (or set EVOLUTION_API_KEY)")
    parser.add_argument("--model", help="Bedrock model ID (e.g., anthropic.claude-opus-4-5-20251101-v1:0)")
    parser.add_argument("--show-config", action="store_true", help="Show current provider configuration and exit")

    args = parser.parse_args()

    # Show config and exit if requested
    if args.show_config:
        print_current_config()
        return

    # Validate required args for running
    if not args.agent:
        parser.error("--agent is required (unless using --show-config)")
    if not args.instruction:
        parser.error("--instruction is required")
    if not args.working_directory:
        parser.error("--working-directory is required")

    # Get model from args, env, or config
    model = args.model
    if not model:
        # Check config for this phase/agent
        _, config_model = get_provider_for_phase(args.agent.capitalize())
        model = config_model

    print(f"🔌 Connecting to Local Hands at {args.daemon_url}...")

    # 1. Initialize Remote Tool Executor (The Hands)
    executor = RemoteToolExecutor(
        daemon_url=args.daemon_url,
        working_directory=args.working_directory,
        api_key=args.api_key or os.environ.get("EVOLUTION_API_KEY")
    )

    # 2. Initialize LLM Provider (The Brain)
    print(f"🧠 Initializing Cloud Brain (Bedrock)...")
    if model:
        print(f"   Model: {model}")
    else:
        print(f"   Model: (provider default)")

    llm_provider = BedrockProvider(tool_executor=executor.execute)

    # 3. Initialize Agent
    agent = None
    agent_lower = args.agent.lower()

    if agent_lower == "architect":
        agent = ArchitectAgent(llm_provider=llm_provider)
    elif agent_lower == "builder":
        agent = BuilderAgent(llm_provider=llm_provider)
    elif agent_lower == "scout":
        from tools.evolution.agents.scout_agent import ScoutAgent
        # Scout needs project_root, but we can pass a dummy path since it will use RemoteToolExecutor mostly
        # However, Scout's scan() method is currently local-only (Python code).
        # To run Scout in the cloud, we would need to port scan() to use RemoteToolExecutor for every file op.
        # For now, we'll instantiate it but warn that it might not work fully remotely yet.
        print("⚠️  Warning: Scout agent's scan() method uses local file operations. Some features may not work remotely.")
        agent = ScoutAgent(project_root=Path(args.working_directory), llm_provider=llm_provider)
    else:
        # Generic Agent for any other phase
        from tools.evolution.agents.generic_agent import GenericAgent
        agent = GenericAgent(name=args.agent, llm_provider=llm_provider)

    # 4. Run Agent
    print(f"🚀 Running {agent.name} Agent...")

    def event_callback(event):
        # Simple logging of events
        if event.get("type") == "assistant":
            content = event.get("message", {}).get("content", [])
            for block in content:
                if block.get("type") == "text":
                    print(block.get("text"), end="", flush=True)
        elif event.get("type") == "tool_use":
            print(f"\n🛠️  Tool Use: {event.get('tool')} {event.get('input')}")
        elif event.get("type") == "tool_result":
            print(f"\n✅ Tool Result: {str(event.get('output'))[:100]}...")

    try:
        result = agent.run(
            working_directory=args.working_directory,  # Pass as string to avoid cross-platform Path issues
            instruction=args.instruction,
            context={"model": model} if model else None,  # Pass model to agent
            event_callback=event_callback
        )
        print("\n\n✨ Execution Complete!")
        print(f"Result: {result}")

    except Exception as e:
        print(f"\n❌ Execution Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
