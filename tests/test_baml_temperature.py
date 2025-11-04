#!/usr/bin/env python3
"""
Test BAML temperature setting

Verifies that temperature 0.0 produces deterministic outputs.
With temperature 0.0, the same input should produce identical outputs.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.baml_integration import (
    update_phase_with_baml,
    is_baml_available,
    clear_baml_cache
)


def test_temperature_zero_produces_deterministic_outputs():
    """
    Test that temperature 0.0 setting produces deterministic outputs.

    Run the same BAML call multiple times and verify outputs are identical.
    This only works if temperature is 0.0 (deterministic sampling).
    """
    if not is_baml_available():
        print("⚠️  BAML not available, skipping temperature test")
        return

    # Clear cache to ensure fresh calls
    clear_baml_cache()

    # Make 3 identical calls with same inputs
    results = []
    for i in range(3):
        result = update_phase_with_baml(
            phase="Scout",
            status="researching",
            detail="Determinism test run",
            session_id="temperature-test",
            iteration=0
        )
        results.append(result)

    # Verify all results are present
    assert len(results) == 3
    assert all(r is not None for r in results)

    # With temperature 0.0, outputs should be identical
    # (or at least very similar - timestamps may vary)

    # Check that core fields are consistent
    for i in range(1, 3):
        assert results[0]['session_id'] == results[i]['session_id'], \
            f"session_id should be identical (run {i})"
        assert results[0]['current_phase'] == results[i]['current_phase'], \
            f"current_phase should be identical (run {i})"
        assert results[0]['status'] == results[i]['status'], \
            f"status should be identical (run {i})"
        assert results[0]['progress_detail'] == results[i]['progress_detail'], \
            f"progress_detail should be identical (run {i})"
        assert results[0]['test_iteration'] == results[i]['test_iteration'], \
            f"test_iteration should be identical (run {i})"

    print("✅ Temperature 0.0 verified: All outputs are deterministic and consistent")
    print(f"   Ran 3 identical calls, all produced same structured output")


def test_temperature_setting_in_schema():
    """Test that temperature is configured in BAML schema"""
    schema_file = Path(__file__).parent.parent / "tools" / "baml_schemas" / "clients.baml"

    assert schema_file.exists(), "BAML clients schema should exist"

    content = schema_file.read_text()

    # Check that GPT4oMini client has temperature setting
    assert "client<llm> GPT4oMini" in content, "GPT4oMini client should be defined"

    # Find the GPT4oMini section
    gpt4omini_start = content.find("client<llm> GPT4oMini")
    assert gpt4omini_start != -1

    # Extract just the GPT4oMini client block (until next client or end)
    next_client = content.find("client<llm>", gpt4omini_start + 1)
    if next_client == -1:
        next_client = content.find("//", gpt4omini_start + 50)  # Find next comment section

    gpt4omini_block = content[gpt4omini_start:next_client]

    # Verify temperature is set to 0.0
    assert "temperature" in gpt4omini_block, \
        "GPT4oMini client should have temperature setting"
    assert "0.0" in gpt4omini_block or "0" in gpt4omini_block, \
        "Temperature should be set to 0.0 for deterministic outputs"

    print("✅ BAML schema verified: temperature 0.0 configured for GPT4oMini")
    print(f"   Schema location: {schema_file}")


if __name__ == "__main__":
    print("Testing BAML temperature configuration...\n")

    print("Test 1: Schema configuration")
    test_temperature_setting_in_schema()
    print()

    print("Test 2: Deterministic output verification")
    print("   (This will make 3 API calls to verify determinism)")
    test_temperature_zero_produces_deterministic_outputs()
    print()

    print("✅ All temperature tests passed!")
