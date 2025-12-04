import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tools.evolution.agents.scout_agent import ScoutAgent
from tools.evolution.agents.architect_agent import ArchitectAgent
from tools.evolution.agents.builder_agent import BuilderAgent
from tools.evolution.framework.llm_provider import LocalClaudeProvider

def verify_agents():
    print("🔍 Verifying Agent Classes...")
    
    # Verify ScoutAgent
    try:
        scout = ScoutAgent(project_root)
        print(f"✅ ScoutAgent instantiated successfully (Provider: {type(scout.llm_provider).__name__})")
    except Exception as e:
        print(f"❌ ScoutAgent instantiation failed: {e}")

    # Verify ArchitectAgent
    try:
        architect = ArchitectAgent()
        print(f"✅ ArchitectAgent instantiated successfully (Provider: {type(architect.llm_provider).__name__})")
        # Check if it can find its default prompt (might fail if file doesn't exist, but we want to know)
        try:
            prompt = architect.get_system_prompt()
            print(f"   - Default system prompt: {prompt[:50]}...")
        except Exception as e:
            print(f"   - Note: Default prompt loading check: {e}")
            
    except Exception as e:
        print(f"❌ ArchitectAgent instantiation failed: {e}")

    # Verify BuilderAgent
    try:
        builder = BuilderAgent()
        print(f"✅ BuilderAgent instantiated successfully (Provider: {type(builder.llm_provider).__name__})")
        try:
            prompt = builder.get_system_prompt()
            print(f"   - Default system prompt: {prompt[:50]}...")
        except Exception as e:
            print(f"   - Note: Default prompt loading check: {e}")

    except Exception as e:
        print(f"❌ BuilderAgent instantiation failed: {e}")

    # Verify GenericAgent (e.g., for Test phase)
    try:
        from tools.evolution.agents.generic_agent import GenericAgent
        test_agent = GenericAgent("Test")
        print(f"✅ GenericAgent (Test) instantiated successfully (Provider: {type(test_agent.llm_provider).__name__})")
        print(f"   - Default system prompt: {test_agent.get_system_prompt()[:50]}...")
    except Exception as e:
        print(f"❌ GenericAgent instantiation failed: {e}")

if __name__ == "__main__":
    verify_agents()
