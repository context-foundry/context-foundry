"""
Mindcraft Planner Engine

Handles goal generation, prioritization, and assignment.
Uses LLM to strategize based on world state.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import shutil

from .goals import Goal, GoalStatus, GoalType
from .models import AgentState, AgentStatus
from .monitor import MindcraftMonitor
from .learner import MindcraftLearner

# Import standard library
import asyncio

PROMPTS_DIR = Path(__file__).parent / "prompts"


class MindcraftPlanner:
    """
    Strategic brain of the operation.
    Manages the goal queue and dispatches tasks to agents.
    """

    def __init__(self, monitor: MindcraftMonitor, dry_run: bool = False):
        self.monitor = monitor
        self.dry_run = dry_run
        self.learner = MindcraftLearner()  # Initialize Knowledge Base

        self.goals: Dict[str, Goal] = {}  # All goals by ID
        self.active_goal_ids: List[str] = []
        self.pending_goal_ids: List[str] = []
        self.completed_goal_ids: List[str] = []

        self.planning_interval = 300  # 5 minutes
        self.last_planning_time = 0

        # Load system prompt
        try:
            with open(PROMPTS_DIR / "planner_system.md", "r") as f:
                self.system_prompt = f.read()
        except FileNotFoundError:
            self.system_prompt = "You are Mindcraft Overlord. Generate goals."

    def add_goal(self, goal: Goal) -> str:
        """Add a new goal to the system."""
        self.goals[goal.id] = goal
        self.pending_goal_ids.append(goal.id)
        self._sort_pending_goals()
        return goal.id

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """Retrieve a goal by ID."""
        return self.goals.get(goal_id)

    def _sort_pending_goals(self):
        """Sort pending goals by priority (descending)."""
        self.pending_goal_ids.sort(
            key=lambda gid: self.goals[gid].priority, reverse=True
        )

    def update(self):
        """
        Main planning tick.
        Checks world state, manages goals, triggers LLM if needed.
        """
        now = time.time()

        # 1. Check active goals for completion
        self._check_active_goals()

        # 2. Assign pending goals if agents available
        self._assign_goals()

        # 3. Replenish goals if needed (LLM call)
        if len(self.pending_goal_ids) == 0 or (
            now - self.last_planning_time > self.planning_interval
        ):
            if not self.dry_run:
                # In dry run, we don't auto-call LLM to save tokens
                # Use explicit trigger method instead
                self.last_planning_time = now
                # self.run_llm_planning() - Async handling needed here
                pass

    def _check_active_goals(self):
        """Check status of currently running goals."""
        for gid in self.active_goal_ids[:]:  # Copy list to modify during iteration
            goal = self.goals[gid]
            agent = self.monitor.client.get_agent_status(goal.assigned_agent)

            if not agent:
                continue

            # Simple criteria check: Inventory
            # Example criteria: {"inventory": {"oak_log": 64}}
            if "inventory" in goal.criteria:
                if self._check_inventory_criteria(agent, goal.criteria["inventory"]):
                    self._complete_goal(goal)

    def _check_inventory_criteria(
        self, agent: AgentState, required_items: Dict[str, int]
    ) -> bool:
        """Check if agent's inventory meets requirements."""
        # Simplify inventory check for now
        # Flatten agent inventory list to dict
        agent_inv = {}
        for item in agent.inventory:
            name = item.get("name")
            count = item.get("count", 0)
            agent_inv[name] = agent_inv.get(name, 0) + count

        for req_name, req_count in required_items.items():
            if agent_inv.get(req_name, 0) < req_count:
                return False
        return True

    def _complete_goal(self, goal: Goal):
        """Mark a goal as complete."""
        goal.status = GoalStatus.COMPLETED
        goal.completed_at = datetime.now()

        if goal.id in self.active_goal_ids:
            self.active_goal_ids.remove(goal.id)
        self.completed_goal_ids.append(goal.id)
        print(f"✅ Goal Completed: {goal.description} ({goal.assigned_agent})")

        # Log to persistence
        self.monitor.persistence.save_history(
            "goal_complete",
            {
                "goal_id": goal.id,
                "description": goal.description,
                "agent": goal.assigned_agent,
            },
        )

    def _assign_goals(self):
        """Assign highest priority pending goals to free agents."""
        agents = self.monitor.client.get_all_agents()

        # Find free agents
        busy_agents = {self.goals[gid].assigned_agent for gid in self.active_goal_ids}
        free_agents = [
            name
            for name, agent in agents.items()
            if agent.status == AgentStatus.ONLINE and name not in busy_agents
        ]

        if not free_agents:
            return

        # Assign goals
        # We need to iterate carefully since we modify the lists
        while free_agents and self.pending_goal_ids:
            agent_name = free_agents.pop(0)
            goal_id = self.pending_goal_ids.pop(0)
            goal = self.goals[goal_id]

            goal.status = GoalStatus.ACTIVE
            goal.assigned_agent = agent_name
            goal.started_at = datetime.now()

            self.active_goal_ids.append(goal_id)
            print(f"🚀 Assigned Goal: {goal.description} -> {agent_name}")

            # Send command to agent?
            # In Phase 4 we will translate Goal -> Commands
            # For now, just logging content

    async def run_llm_planning(self) -> List[Goal]:
        """
        Call LLM to generate new goals based on world state.

        Returns:
            List of generated Goal objects
        """
        print("🧠 Thinking (Planning)...")

        # 1. Prepare Context
        agents = {
            name: state.to_dict()
            for name, state in self.monitor.client.get_all_agents().items()
        }
        active_goals = [self.goals[gid].to_dict() for gid in self.active_goal_ids]

        context = {
            "world_time": 1000,  # Placeholder, needs world state source
            "agents": agents,
            "active_goals": active_goals,
            "completed_goals_count": len(self.completed_goal_ids),
        }

        input_json = json.dumps(context, indent=2)

        # 2. Call Claude CLI
        # In dry_run, we return a mock response
        if self.dry_run:
            print("  (Dry Run: returning mock goals)")
            mock_goals = [
                Goal(
                    description="Gather 32 Dirt (Mock)",
                    type=GoalType.GATHER,
                    priority=80,
                    criteria={"inventory": {"dirt": 32}},
                )
            ]
            for g in mock_goals:
                self.add_goal(g)
            return mock_goals

        # Real LLM Call
        # We use `claude` CLI via subprocess
        try:
            # Check if claude is available
            if not shutil.which("claude"):
                print("Error: `claude` CLI not found")
                return []

            # Extract context tags using heuristics
            context_tags = []

            # Time-based tags
            # (Assuming we get time from somewhere, for now defaulting to day)
            # context_tags.append("day")

            # Check for water near agents
            for agent in agents.values():
                biome = agent.get("biome", "").lower()
                if "ocean" in biome or "river" in biome:
                    context_tags.append("water")
                    context_tags.append("ocean")

            # Simple retrieval
            patterns_text = self.learner.get_pattern_summary(context_tags)

            full_prompt = (
                f"{self.system_prompt}\n\n{patterns_text}\n\nINPUT DATA:\n{input_json}"
            )

            process = await asyncio.create_subprocess_exec(
                "claude",
                "--message",
                full_prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                print(f"LLM Error: {stderr.decode()}")
                return []

            response_text = stdout.decode()

            # 3. Parse Response
            # Simple extraction of JSON block
            try:
                # Find start/end of JSON
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start == -1 or end == 0:
                    print("LLM Error: No JSON found in response")
                    return []

                json_str = response_text[start:end]
                data = json.loads(json_str)

                new_goals = []
                for g_data in data.get("new_goals", []):
                    goal = Goal(
                        description=g_data.get("description", "Unknown Goal"),
                        type=GoalType(g_data.get("type", "idle")),
                        priority=g_data.get("priority", 50),
                        criteria=g_data.get("criteria", {}),
                        parameters=g_data.get("parameters", {}),
                    )
                    self.add_goal(goal)
                    new_goals.append(goal)

                return new_goals

            except json.JSONDecodeError as e:
                print(f"LLM Error: Invalid JSON: {e}")
                return []

        except Exception as e:
            print(f"Planning Error: {e}")
            return []
