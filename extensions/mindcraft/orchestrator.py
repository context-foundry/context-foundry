"""
Mindcraft Orchestrator

The "Main Loop" of factors.
Initializes and coordinates Client, Monitor, and Planner.
"""

import asyncio
import signal
import sys
from typing import Optional

from .client import MindcraftClient
from .monitor import MindcraftMonitor
from .planner import MindcraftPlanner
from .detector import detect_mindcraft_config
from .persistence import MindcraftPersistence


class MindcraftOrchestrator:
    """
    Main orchestration engine.
    Binds the Body (Client), Eyes (Monitor), and Brain (Planner) together.
    """

    def __init__(self, dry_run: bool = False, server_url: Optional[str] = None):
        # Load config
        self.config = detect_mindcraft_config() or {}

        # Overrides
        if dry_run:
            self.config["dry_run"] = True
        if server_url:
            self.config["server_url"] = server_url

        self.dry_run = self.config.get("dry_run", False)
        server = self.config.get("server_url", "ws://localhost:8080")

        print(f"🔧 Initializing Mindcraft Orchestrator (Dry Run: {self.dry_run})")
        print(f"   Server: {server}")

        # Components
        self.client = MindcraftClient(server_url=server, dry_run=self.dry_run)
        self.persistence = MindcraftPersistence()
        self.monitor = MindcraftMonitor(
            client=self.client, persistence=self.persistence
        )
        self.planner = MindcraftPlanner(monitor=self.monitor, dry_run=self.dry_run)

        self._running = False
        self._loop_task: Optional[asyncio.Task] = None

        # Stuck detection nudge settings
        self._last_nudge_time: dict = {}  # agent -> timestamp
        self.NUDGE_COOLDOWN = 300  # Seconds between nudges per agent (5 min)
        self.STUCK_NUDGE_THRESHOLD = 120  # Stuck count before nudging (2 min of checks)

        # Autonomous goal loop settings
        self._last_goal_time: dict = {}  # agent -> timestamp
        self.GOAL_CHECK_INTERVAL = 300  # Check every 5 minutes if agent needs a goal
        self._goal_cycle: dict = {}  # agent -> cycle index
        self._agent_is_busy: dict = {}  # agent -> bool tracking if working on goal

        # Vision scan settings
        self._last_vision_time: dict = {}  # agent -> timestamp
        self.VISION_SCAN_INTERVAL = 300  # Request vision scan every 5 minutes

        # Home base settings - Andy should stay near spawn
        self.HOME_BASE = {"x": 288, "y": 80, "z": -48}  # World spawn point
        self.MAX_DISTANCE_FROM_HOME = 150  # Blocks - if further, return home
        self._last_home_check: dict = {}  # agent -> timestamp
        self.HOME_CHECK_INTERVAL = 60  # Check every 60 seconds

        # Goal definitions: (name, priority, commands/messages)
        self.GOAL_ROTATION = [
            # Phase 1: Gather wood
            {
                "name": "gather_wood",
                "message": "[TASK] Gather 32 logs now. Execute this: !collectBlocks('birch_log', 32)",
            },
            # Phase 2: Build something with wood
            {
                "name": "build_wood_structure",
                "message": "[TASK] Build a wooden shelter. Execute: !newAction('Build a 5x5 wooden shelter with walls, door, and roof using planks')",
            },
            # Phase 3: Gather stone/cobblestone
            {
                "name": "gather_stone",
                "message": "[TASK] Mine 64 stone blocks now. Execute this: !collectBlocks('stone', 64)",
            },
            # Phase 4: Build with stone
            {
                "name": "build_stone_structure",
                "message": "[TASK] Build stone walls. Execute: !newAction('Reinforce shelter with cobblestone walls and add torches inside')",
            },
            # Phase 5: Gather food
            {
                "name": "gather_food",
                "message": "[TASK] You need food. Hunt animals now. Execute: !attack('pig')",
            },
            # Phase 6: Explore and scout
            {
                "name": "explore",
                "message": "[TASK] Scout the area. Execute: !vision then explore in a promising direction.",
            },
        ]

    async def start(self):
        """Start the full orchestration system."""
        if self._running:
            return

        print("🚀 Starting Mindcraft System...")

        # 1. Connect Client
        print("   Connecting to MindServer...")
        if not await self.client.connect():
            print("❌ Failed to connect. Exiting.")
            return

        # 2. Start Monitor
        print("   Starting Monitor...")
        await self.monitor.start()

        # 3. Start Loop
        self._running = True
        self._loop_task = asyncio.create_task(self._main_loop())

        print("✅ System Online and Running!")

        # Keep running until stopped
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self):
        """Gracefully stop the system."""
        print("\n🛑 Stopping Mindcraft System...")
        self._running = False

        if self._loop_task:
            self._loop_task.cancel()

        await self.monitor.stop()
        await self.client.disconnect()
        print("✅ System Stopped.")

    async def _main_loop(self):
        """The heartbeat of the system."""
        import time
        print("💓 Main loop active")

        while self._running:
            try:
                # 1. Update Planner (Strategize)
                # This checks goals, assigns tasks, and may trigger LLM
                self.planner.update()

                # 2. Check for stuck agents and nudge them
                await self._check_and_nudge_stuck_agents()

                # 3. Check for idle agents and assign new goals
                await self._check_and_assign_goals()

                # 4. Request periodic vision scans for environmental awareness
                await self._request_vision_scans()

                # 5. Check if agents are too far from home and recall them
                await self._check_distance_from_home()

                # 6. Sleep tick
                # Detailed work happens in background tasks (monitor, etc)
                await asyncio.sleep(1.0)

            except Exception as e:
                print(f"⚠️ Error in main loop: {e}")
                await asyncio.sleep(1.0)

    async def _check_and_nudge_stuck_agents(self):
        """Check for stuck agents and send a nudge if needed."""
        import time

        monitor_status = self.monitor.get_monitor_status()
        stuck_counts = monitor_status.get("stuck_counts", {})

        for agent_name, count in stuck_counts.items():
            if count >= self.STUCK_NUDGE_THRESHOLD:
                # Check cooldown
                last_nudge = self._last_nudge_time.get(agent_name, 0)
                now = time.time()

                if now - last_nudge >= self.NUDGE_COOLDOWN:
                    print(f"🔔 Nudging stuck agent: {agent_name} (stuck for {count} checks)")
                    await self._send_nudge(agent_name)
                    self._last_nudge_time[agent_name] = now

    async def _send_nudge(self, agent_name: str):
        """Send a nudge message to help a stuck agent."""
        nudge_messages = [
            "Hey, are you stuck? Try looking around and finding another way.",
            "Status check - what are you working on right now?",
            "I noticed you haven't moved in a while. Do you need help?",
            "If you're stuck in a hole, try placing blocks to climb out. What's your situation?",
        ]
        import random
        message = random.choice(nudge_messages)

        await self.client.send_message(agent_name, message)
        print(f"   Sent: '{message}'")

    async def _check_and_assign_goals(self):
        """Check for idle agents and assign new goals from the rotation."""
        import time

        # Get all known agents
        agents = self.client.get_all_agents()
        if not agents:
            return

        now = time.time()

        for agent_name, agent_state in agents.items():
            # Skip offline agents
            if agent_state.status.value != "online":
                continue

            # Initialize tracking for new agents - give them their first goal right away
            if agent_name not in self._last_goal_time:
                self._last_goal_time[agent_name] = now
                self._goal_cycle[agent_name] = 0
                self._agent_is_busy[agent_name] = False

                # Send first goal immediately
                goal = self.GOAL_ROTATION[0]
                print(f"\n🎯 Initializing {agent_name} with first goal: {goal['name']}")
                await self.client.send_message(agent_name, goal["message"])
                self._goal_cycle[agent_name] = 1
                continue

            # Check if enough time has passed since last goal
            # Use GOAL_CHECK_INTERVAL (default 2 minutes) as the cycle time
            time_since_goal = now - self._last_goal_time[agent_name]
            if time_since_goal < self.GOAL_CHECK_INTERVAL:
                continue

            # Time for a new goal!
            cycle_index = self._goal_cycle.get(agent_name, 0)
            goal = self.GOAL_ROTATION[cycle_index % len(self.GOAL_ROTATION)]

            print(f"\n🎯 Assigning new goal to {agent_name}: {goal['name']}")
            await self.client.send_message(agent_name, goal["message"])

            # Update tracking
            self._last_goal_time[agent_name] = now
            self._goal_cycle[agent_name] = cycle_index + 1
            print(f"   Next goal will be: {self.GOAL_ROTATION[(cycle_index + 1) % len(self.GOAL_ROTATION)]['name']}")

    async def _request_vision_scans(self):
        """Request periodic vision scans to give agents environmental awareness."""
        import time

        # Get all known agents
        agents = self.client.get_all_agents()
        if not agents:
            return

        now = time.time()

        for agent_name, agent_state in agents.items():
            # Skip offline agents
            if agent_state.status.value != "online":
                continue

            # Initialize tracking for new agents
            if agent_name not in self._last_vision_time:
                self._last_vision_time[agent_name] = now
                continue

            # Check if enough time has passed since last vision scan
            time_since_scan = now - self._last_vision_time[agent_name]
            if time_since_scan < self.VISION_SCAN_INTERVAL:
                continue

            # Vision HUD is now built into agent state - no need to request scans
            # Just update the timestamp to track when we would have requested
            self._last_vision_time[agent_name] = now

    async def _check_distance_from_home(self):
        """Check if agents are too far from home base and recall them."""
        import time
        import math

        now = time.time()
        monitor_status = self.monitor.get_monitor_status()
        agent_states = monitor_status.get("agent_states", {})

        for agent_name, state in agent_states.items():
            # Initialize home check time if not set
            if agent_name not in self._last_home_check:
                self._last_home_check[agent_name] = now
                continue

            # Only check every HOME_CHECK_INTERVAL seconds
            time_since_check = now - self._last_home_check[agent_name]
            if time_since_check < self.HOME_CHECK_INTERVAL:
                continue

            self._last_home_check[agent_name] = now

            # Get agent position from state
            position = state.get("position", {})
            if not position:
                continue

            agent_x = position.get("x", 0)
            agent_z = position.get("z", 0)

            # Calculate distance from home (2D, ignore Y)
            dx = agent_x - self.HOME_BASE["x"]
            dz = agent_z - self.HOME_BASE["z"]
            distance = math.sqrt(dx * dx + dz * dz)

            if distance > self.MAX_DISTANCE_FROM_HOME:
                print(f"🏠 {agent_name} is {int(distance)} blocks from home (max: {self.MAX_DISTANCE_FROM_HOME})")
                print(f"   Sending recall command...")

                home_x = self.HOME_BASE["x"]
                home_z = self.HOME_BASE["z"]
                await self.client.send_message(
                    agent_name,
                    f"You've wandered too far from home base! Return towards spawn at coordinates X={home_x}, Z={home_z}. "
                    f"Execute: !goToCoordinates({home_x}, 80, {home_z}, 1)"
                )


async def run_orchestrator(dry_run: bool = False, server_url: Optional[str] = None):
    """Entry point helper."""
    orchestrator = MindcraftOrchestrator(dry_run=dry_run, server_url=server_url)

    # Handle signals
    loop = asyncio.get_running_loop()

    def handle_signal():
        print("\nReceived stop signal")
        asyncio.create_task(orchestrator.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    await orchestrator.start()


if __name__ == "__main__":
    # Simple CLI for direct testing
    dry_run_arg = "--dry-run" in sys.argv
    asyncio.run(run_orchestrator(dry_run=dry_run_arg))
