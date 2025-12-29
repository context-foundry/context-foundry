"""
Test Suite for Mindcraft Phase 2: State Awareness

Tests:
1. Data Models (serialization/deserialization)
2. Persistence (save/load state)
3. Monitor (update loop, anomaly detection)
"""

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

# Fix imports to allow running from root
import sys

sys.path.append(str(Path(__file__).parent.parent))

from extensions.mindcraft.models import AgentState, AgentStatus
from extensions.mindcraft.persistence import MindcraftPersistence
from extensions.mindcraft.monitor import MindcraftMonitor
from extensions.mindcraft.client import MindcraftClient


class TestMindcraftPhase2(unittest.TestCase):
    def setUp(self):
        # Create temp directory for persistence tests
        self.test_dir = Path(tempfile.mkdtemp())
        self.persistence = MindcraftPersistence(base_dir=self.test_dir)

    def tearDown(self):
        # Clean up temp directory
        shutil.rmtree(self.test_dir)

    def test_agent_state_model(self):
        """Test AgentState serialization and deserialization."""
        print("\nTesting Data Models...")
        original = AgentState(
            name="test_bot",
            status=AgentStatus.ONLINE,
            health=15.5,
            position=(100, 64, -200),
            inventory=[{"name": "stone", "count": 64}],
        )

        # Serialize
        data = original.to_dict()
        self.assertEqual(data["name"], "test_bot")
        self.assertEqual(data["status"], "online")
        self.assertEqual(data["position"], [100, 64, -200])

        # Deserialize
        restored = AgentState.from_dict(data)
        self.assertEqual(restored.name, original.name)
        self.assertEqual(restored.status, original.status)
        self.assertEqual(restored.health, original.health)
        self.assertEqual(list(restored.position), list(original.position))
        print("✅ Data Models OK")

    def test_persistence(self):
        """Test saving and loading agent state."""
        print("\nTesting Persistence...")
        state = AgentState(name="andy", status=AgentStatus.ONLINE)

        # Save
        self.persistence.save_agent_state(state)

        # Verify file exists
        expected_file = self.test_dir / "state" / "andy_state.json"
        self.assertTrue(expected_file.exists())

        # Load
        loaded = self.persistence.load_agent_state("andy")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "andy")
        self.assertEqual(loaded.status, AgentStatus.ONLINE)
        print("✅ Persistence OK")

    def test_monitor_integration(self):
        """Test Monitor integration with Client and Persistence."""
        print("\nTesting Monitor Integration...")

        async def run_async_test():
            # Setup mocked client
            client = MindcraftClient(dry_run=True)
            monitor = MindcraftMonitor(
                client=client, persistence=self.persistence, check_interval=0.1
            )

            # Start monitor
            await monitor.start()

            # Simulate state update via client
            await client.connect()
            update_data = {
                "name": "andy",
                "health": 18.0,
                "position": {"x": 10, "y": 64, "z": 10},
            }
            # Manually trigger client's internal handler which fires events
            # In a real scenario, this comes from socket.io
            client._handle_state_update(update_data)

            # Wait a moment for async processing
            await asyncio.sleep(0.2)

            # Verify persistence was updated
            saved = self.persistence.load_agent_state("andy")
            self.assertIsNotNone(saved)
            self.assertEqual(saved.health, 18.0)

            # Stop monitor
            await monitor.stop()
            await client.disconnect()

        # Run async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_async_test())
        loop.close()
        print("✅ Monitor Integration OK")


if __name__ == "__main__":
    unittest.main()
