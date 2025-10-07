#!/usr/bin/env python3
"""
Test script for multi-agent orchestrator.

Simple test to verify the system works end-to-end.
"""

import sys
from pathlib import Path

# Add parent directory to path
FOUNDRY_ROOT = Path(__file__).parent.parent
sys.path.append(str(FOUNDRY_ROOT))

from workflows.multi_agent_orchestrator import MultiAgentOrchestrator


def test_simple_project():
    """Test with a simple project."""

    print("="*60)
    print("Testing Multi-Agent Orchestrator")
    print("="*60)
    print("\nThis test will create a simple calculator project")
    print("to verify the multi-agent system works end-to-end.\n")

    orchestrator = MultiAgentOrchestrator(
        project_name="test-calculator",
        task_description="Build a simple Python calculator with add, subtract, multiply, and divide functions. Include unit tests.",
        enable_checkpointing=True,
        enable_self_healing=True,
        max_healing_attempts=2
    )

    result = orchestrator.run()

    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)

    if result['success']:
        print("✅ Test PASSED!")
        print(f"\nProject created at: {result['project_dir']}")
        print(f"Session logs at: {result['session_dir']}")

        # Print metrics
        metrics = result.get('metrics', {})
        print(f"\nMetrics:")
        print(f"  Total tokens: {metrics.get('token_usage', {}).get('total', 0):,}")

        phases = metrics.get('phases', {})
        for phase, data in phases.items():
            print(f"  {phase}: {data.get('duration', 0):.1f}s, {data.get('tokens', 0):,} tokens")

    else:
        print("❌ Test FAILED!")
        print(f"Error: {result.get('error', 'Unknown error')}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = test_simple_project()
    sys.exit(exit_code)
