import os
import sys
import json
from pathlib import Path

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.evolution.framework.llm_provider import BedrockAgentProvider
from tools.evolution.communication.tool_executor import ToolExecutor

def main():
    print("Verifying Bedrock Agent...")
    
    # Configuration
    AGENT_ID = "741G0KKAZV"
    ALIAS_ID = "LFWCBM2B3E"
    
    # Initialize Tool Executor (mock or real)
    # We'll use a simple local executor for this test
    def local_executor(tool_name, tool_input):
        print(f"[Tool Execution] {tool_name} with input: {tool_input}")
        if tool_name == "list_directory":
            return str(os.listdir(tool_input.get("path", ".")))
        elif tool_name == "run_command":
            return "Command executed successfully (mock)"
        return "Tool not found"

    # Initialize Provider
    provider = BedrockAgentProvider(
        agent_id=AGENT_ID,
        agent_alias_id=ALIAS_ID,
        tool_executor=local_executor,
        region="us-east-1"
    )
    
    # Test Query
    query = "List the files in the current directory."
    print(f"Sending query: '{query}'")
    
    try:
        response = provider.generate(
            system_prompt="You are a helpful assistant.",
            user_prompt=query
        )
        print("\n--- Response ---")
        print(response)
        print("----------------")
        
        if "verify_agent.py" in response or "tools" in response or "[" in response:
             print("\n✅ Verification Successful: Agent likely used the tool or returned file list.")
        else:
             print("\n⚠️ Verification Warning: Response might not contain file list. Check output.")

    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
