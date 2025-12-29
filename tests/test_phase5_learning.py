"""
Test Suite for Mindcraft Phase 5: Pattern Learning

Tests:
1. Pattern Loading (Learner)
2. Context Matching (Tags -> Pattern)
3. Planner Integration (Learner initialization)
"""

import unittest
import sys
from pathlib import Path

# Fix imports
sys.path.append(str(Path(__file__).parent.parent))

from extensions.mindcraft.learner import MindcraftLearner
from extensions.mindcraft.planner import MindcraftPlanner
from extensions.mindcraft.monitor import MindcraftMonitor
from extensions.mindcraft.client import MindcraftClient


class TestMindcraftLearning(unittest.TestCase):
    def setUp(self):
        self.learner = MindcraftLearner()

    def test_load_patterns(self):
        """Test that patterns are loaded from JSON."""
        print("\nTesting Pattern Loading...")
        self.assertTrue(len(self.learner.patterns) > 0, "Should load default patterns")

        # Verify specific pattern exists
        water_rule = next(
            (p for p in self.learner.patterns if p["id"] == "mc-001"), None
        )
        self.assertIsNotNone(water_rule)
        self.assertEqual(water_rule["name"], "Water Avoidance")
        print("✅ Pattern Loading OK")

    def test_find_relevant(self):
        """Test finding patterns by tag."""
        print("\nTesting Context Matching...")

        # Case 1: Water context
        matches = self.learner.find_relevant(["water", "mining"])
        self.assertTrue(len(matches) > 0)
        self.assertEqual(matches[0]["id"], "mc-001", "Should find Water Avoidance rule")

        # Case 2: Night context
        matches = self.learner.find_relevant(["night"])
        self.assertTrue(len(matches) > 0)
        self.assertEqual(matches[0]["id"], "mc-002", "Should find Night Survival rule")

        # Case 3: Irrelevant context
        matches = self.learner.find_relevant(["space", "lasers"])
        self.assertEqual(len(matches), 0, "Should find no matches")
        print("✅ Context Matching OK")

    def test_planner_integration(self):
        """Test that Planner initializes Learner."""
        print("\nTesting Planner Integration...")
        client = MindcraftClient(dry_run=True)
        monitor = MindcraftMonitor(client=client)
        planner = MindcraftPlanner(monitor=monitor, dry_run=True)

        self.assertIsNotNone(planner.learner, "Planner should have a Learner instance")
        self.assertTrue(
            len(planner.learner.patterns) > 0,
            "Planner's Learner should have loaded patterns",
        )
        print("✅ Planner Integration OK")


if __name__ == "__main__":
    unittest.main()
