
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path("/Users/name/homelab/context-foundry")
sys.path.insert(0, str(project_root))

from tools.evolution.framework.provider_config import get_provider_for_phase, print_current_config

print("Testing Provider Resolution...")
print(f"Config file: {Path.home() / '.context-foundry/provider_config.json'}")

print("\n--- Current Config ---")
print_current_config()

print("\n--- Resolution for 'Builder' ---")
provider, model, extra = get_provider_for_phase("Builder")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"Extra: {extra}")

if provider == "bedrock-agent":
    print("SUCCESS: Resolved to bedrock-agent")
else:
    print("FAILURE: Did not resolve to bedrock-agent")
