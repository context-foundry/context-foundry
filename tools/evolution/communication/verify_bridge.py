"""
Verify Communication Bridge Components.
"""

import sys
from pathlib import Path
import shutil

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tools.evolution.communication.tool_executor import ToolExecutor

def verify_local_executor():
    print("🔍 Verifying ToolExecutor...")
    
    test_dir = project_root / "tmp" / "bridge_test"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        executor = ToolExecutor(test_dir)
        
        # Test 1: Run Command
        print("   Testing run_command...", end="")
        result = executor.execute("run_command", {"command": "echo 'Hello Bridge'"})
        if result["status"] == "success" and "Hello Bridge" in result["output"]:
            print(" ✅")
        else:
            print(f" ❌ Failed: {result}")
            
        # Test 2: Write File
        print("   Testing write_file...", end="")
        result = executor.execute("write_file", {"path": "test.txt", "content": "Bridge Content"})
        if result["status"] == "success":
            print(" ✅")
        else:
            print(f" ❌ Failed: {result}")
            
        # Test 3: Read File
        print("   Testing read_file...", end="")
        result = executor.execute("read_file", {"path": "test.txt"})
        if result["status"] == "success" and result["output"] == "Bridge Content":
            print(" ✅")
        else:
            print(f" ❌ Failed: {result}")
            
        # Test 4: List Directory
        print("   Testing list_directory...", end="")
        result = executor.execute("list_directory", {"path": "."})
        if result["status"] == "success" and "test.txt" in result["output"]:
            print(" ✅")
        else:
            print(f" ❌ Failed: {result}")

    finally:
        # Cleanup
        if test_dir.exists():
            shutil.rmtree(test_dir)

if __name__ == "__main__":
    verify_local_executor()
