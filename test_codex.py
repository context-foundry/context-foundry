
import sys
from pathlib import Path

# Add project root to path
project_root = Path("/Users/name/homelab/context-foundry")
sys.path.insert(0, str(project_root))

try:
    from tools.mcp_utils.codex import codex_search, codex_get_entry
    print("SUCCESS: Imported codex module")
except ImportError as e:
    print(f"FAILURE: Could not import codex module: {e}")
    sys.exit(1)

print("\n--- Testing Search ---")
# Search for something likely in common-issues.json
results = codex_search("datastore", category="common-issues")
entries = results.get("entries", [])
print(f"Found {len(entries)} entries for 'datastore'")
for entry in entries[:2]:
    print(f"- {entry.get('title')} (ID: {entry.get('id')})")

print("\n--- Testing Get Entry ---")
if entries:
    first_id = entries[0].get("id")
    entry = codex_get_entry(first_id)
    if entry:
        print(f"SUCCESS: Retrieved entry {first_id}")
    else:
        print(f"FAILURE: Could not retrieve entry {first_id}")
else:
    print("Skipping Get Entry test (no search results)")
