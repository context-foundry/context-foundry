"""
Test Suite for Mindcraft Phase 4: Autonomous Loop

Tests:
1. Orchestrator Initialization
2. Dry Run Startup
3. Main Loop Execution (Short Duration)
4. Graceful Shutdown
"""

import asyncio
import unittest
from pathlib import Path
import sys

# Fix imports to allow running from root
sys.path.append(str(Path(__file__).parent.parent))

from extensions.mindcraft.orchestrator import MindcraftOrchestrator
from extensions.mindcraft.client import AgentStatus


class TestMindcraftOrchestration(unittest.TestCase):
    def test_orchestrator_lifecycle(self):
        """Test full orchestrator lifecycle (Start -> Loop -> Stop)."""
        print("\nTesting Orchestrator Lifecycle...")

        async def run_lifecycle():
            # 1. Initialize
            try:
                orch = MindcraftOrchestrator(dry_run=True)
            except Exception as e:
                self.fail(f"Initialization failed: {e}")

            # 2. Start (in background task)
            print("  Starting Orchestrator...")
            task = asyncio.create_task(orch.start())

            # Allow time for startup and a few ticks
            await asyncio.sleep(2.0)

            # 3. Verify System State
            self.assertTrue(orch._running, "Orchestrator should be running")
            self.assertTrue(
                orch.client.is_connected, "Client should be connected (dry run)"
            )

            # Check if agent monitoring is working
            agents = orch.client.get_all_agents()
            self.assertIn("andy", agents)
            self.assertEqual(agents["andy"].status, AgentStatus.ONLINE)
            print("  ✅ System State Verified (Client connected, Agent online)")

            # 4. Stop
            print("  Stopping Orchestrator...")
            await orch.stop()
            await task

            self.assertFalse(orch._running, "Orchestrator should be stopped")
            self.assertFalse(orch.client.is_connected, "Client should be disconnected")
            print("  ✅ Shutdown Verified")

        # Run async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_lifecycle())
        finally:
            loop.close()
        print("✅ Orchestrator Lifecycle OK")


if __name__ == "__main__":
    unittest.main()
