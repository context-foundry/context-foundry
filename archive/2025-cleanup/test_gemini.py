import sys
from pathlib import Path

# Add tools to path
sys.path.append("/Users/name/homelab/context-foundry")

from tools.mcp_utils.phase_execution import run_phase


def test_gemini():
    print("Testing Gemini Integration...")

    # Create a dummy prompt file
    prompt_file = Path("test_prompt.txt")
    prompt_file.write_text(
        "You are a helpful assistant. Reply with 'Gemini is working!'."
    )

    try:
        result = run_phase(
            phase_name="TestGemini",
            phase_prompt_path=prompt_file,
            input_instruction="Say the magic phrase.",
            working_directory=Path("."),
            provider="gemini",
            phase_timeout=60,
        )

        print(f"Exit Code: {result.exit_code}")
        print(f"Status: {result.status}")
        if result.error:
            print(f"Error: {result.error}")

    finally:
        if prompt_file.exists():
            prompt_file.unlink()


if __name__ == "__main__":
    test_gemini()
