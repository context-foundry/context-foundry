import sys
from pathlib import Path

# Add tools to path
sys.path.append("/Users/name/homelab/context-foundry")

from tools.mcp_utils.phase_execution import run_phase


def test_scout():
    print("Testing Scout Phase...")

    prompt_path = Path(
        "/Users/name/homelab/context-foundry/tools/prompts/phases/phase_scout.txt"
    )
    working_dir = Path("/Users/name/homelab/test_multi_provider_debug")
    working_dir.mkdir(parents=True, exist_ok=True)

    result = run_phase(
        phase_name="Scout",
        phase_prompt_path=prompt_path,
        input_instruction="Create a python script fib.py for fibonacci numbers and a separate README.md explaining it.",
        working_directory=working_dir,
        phase_timeout=300,
        provider="claude",
    )

    print(f"Exit Code: {result.exit_code}")
    print(f"Status: {result.status}")
    if result.error:
        print(f"Error: {result.error}")

    # Check if file exists
    report = working_dir / ".context-foundry" / "scout-report.md"
    if report.exists():
        print("✅ Scout report created!")
    else:
        print("❌ Scout report missing!")


if __name__ == "__main__":
    test_scout()
