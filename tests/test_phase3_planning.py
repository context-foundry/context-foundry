"""
Test Suite for Mindcraft Phase 3: Goal Planning

Tests:
1. Goal Queue (FIFO/Priority)
2. Criteria Checking (Inventory updates)
3. Planner update loop
4. LLM Integration (Mock/Dry Run)
"""

import asyncio
import unittest
from pathlib import Path
import sys

# Fix imports to allow running from root
sys.path.append(str(Path(__file__).parent.parent))

from extensions.mindcraft.models import AgentState, AgentStatus
from extensions.mindcraft.goals import Goal, GoalType, GoalStatus
from extensions.mindcraft.planner import MindcraftPlanner
from extensions.mindcraft.client import MindcraftClient
from extensions.mindcraft.monitor import MindcraftMonitor


class TestMindcraftPlanning(unittest.TestCase):
    def setUp(self):
        # Setup clean environment
        self.client = MindcraftClient(dry_run=True)
        self.monitor = MindcraftMonitor(client=self.client)
        self.planner = MindcraftPlanner(monitor=self.monitor, dry_run=True)

        # Setup mock agent
        self.client._agents["andy"] = AgentState(
            name="andy", status=AgentStatus.ONLINE, inventory=[]
        )

    def test_goal_priority_queue(self):
        """Test that high priority goals are assigned first."""
        print("\nTesting Priority Queue...")

        # Add Low Priority Goal
        low_goal = Goal(description="Chill", type=GoalType.IDLE, priority=10)
        self.planner.add_goal(low_goal)

        # Add High Priority Goal
        high_goal = Goal(description="Survive!", type=GoalType.SURVIVE, priority=100)
        self.planner.add_goal(high_goal)

        # Verify Pending Queue Order
        self.assertEqual(
            self.planner.pending_goal_ids[0],
            high_goal.id,
            "High priority should be first",
        )

        # Run Update (Assign)
        self.planner.update()

        # Verify Assignment
        self.assertEqual(self.planner.goals[high_goal.id].status, GoalStatus.ACTIVE)
        self.assertEqual(self.planner.goals[high_goal.id].assigned_agent, "andy")

        # Verify Low Priority is still pending (no free agents)
        self.assertEqual(self.planner.goals[low_goal.id].status, GoalStatus.PENDING)
        print("✅ Priority Queue OK")

    def test_completion_criteria(self):
        """Test that goals complete when criteria are met."""
        print("\nTesting Completion Criteria...")

        # 1. Add Goal: Gather 10 Wood
        goal = Goal(
            description="Gather Wood",
            type=GoalType.GATHER,
            criteria={"inventory": {"oak_log": 10}},
        )
        self.planner.add_goal(goal)

        # 2. Assign Goal
        self.planner.update()
        self.assertEqual(goal.status, GoalStatus.ACTIVE)

        # 3. Update Agent Inventory (Partial)
        self.client._agents["andy"].inventory = [{"name": "oak_log", "count": 5}]
        self.planner.update()
        self.assertEqual(
            goal.status, GoalStatus.ACTIVE, "Goal should still be active (5/10 logs)"
        )

        # 4. Update Agent Inventory (Complete)
        self.client._agents["andy"].inventory = [{"name": "oak_log", "count": 12}]
        self.planner.update()
        self.assertEqual(
            goal.status, GoalStatus.COMPLETED, "Goal should be complete (12/10 logs)"
        )
        print("✅ Completion Criteria OK")

    def test_llm_dry_run(self):
        """Test LLM generation in dry-run mode."""
        print("\nTesting LLM Planning (Dry Run)...")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        goals = loop.run_until_complete(self.planner.run_llm_planning())

        self.assertTrue(len(goals) > 0)
        self.assertEqual(goals[0].type, GoalType.GATHER)
        self.assertTrue("Mock" in goals[0].description)

        loop.close()
        print("✅ LLM Dry Run OK")


if __name__ == "__main__":
    unittest.main()
