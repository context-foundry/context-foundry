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
        self.NUDGE_COOLDOWN = 60  # Seconds between nudges per agent
        self.STUCK_NUDGE_THRESHOLD = 30  # Stuck count before nudging

        # Autonomous goal loop settings
        self._last_goal_time: dict = {}  # agent -> timestamp
        self.GOAL_CHECK_INTERVAL = 120  # Check every 2 minutes if agent needs a goal
        self._goal_cycle: dict = {}  # agent -> cycle index
        self._agent_is_busy: dict = {}  # agent -> bool tracking if working on goal

        # Vision scan settings
        self._last_vision_time: dict = {}  # agent -> timestamp
        self.VISION_SCAN_INTERVAL = 300  # Request vision scan every 5 minutes

        # Goal definitions: (name, priority, commands/messages)
        self.GOAL_ROTATION = [
            # Phase 1: Gather wood
            {
                "name": "gather_wood",
                "message": "Gather wood! Find and collect at least 32 logs. Use !collectBlocks to find oak_log, birch_log, spruce_log, or any other log type. Store extras in a chest if you have one.",
            },
            # Phase 2: Build something with wood
            {
                "name": "build_wood_structure",
                "message": "Build time! Use your wood to craft planks and build a small wooden platform or extend your shelter. Remember: NEVER dig straight down, always place blocks safely.",
            },
            # Phase 3: Gather stone/cobblestone
            {
                "name": "gather_stone",
                "message": "Mine for stone! Find stone or mine existing terrain to collect at least 64 cobblestone. Use !collectBlocks('stone', 64). SAFETY: Never dig straight down, always have a way back up!",
            },
            # Phase 4: Build with stone
            {
                "name": "build_stone_structure",
                "message": "Construction phase! Use your cobblestone to reinforce your shelter, add walls, or build a new structure. Aim for a proper 5x5 house with a door and roof. Place torches for light.",
            },
            # Phase 5: Gather food
            {
                "name": "gather_food",
                "message": "Food run! Hunt for animals (pigs, cows, chickens) or gather crops. Collect at least 16 food items. Use !attack to hunt or !collectBlocks for crops.",
            },
            # Phase 6: Explore and scout
            {
                "name": "explore",
                "message": "Exploration time! Venture out and explore your surroundings. Look for interesting biomes, caves, or resources. Mark interesting locations to return to later. Stay safe!",
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

                # 5. Sleep tick
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
            "Status check - what are you working on? If stuck, try !stop and reassess.",
            "I noticed you haven't moved in a while. Do you need help? Try climbing out or going around obstacles.",
            "Nudge: If you're stuck in a hole, try placing blocks to climb out. What's your situation?",
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

            # Time for a vision scan!
            print(f"\n👁️ Requesting vision scan for {agent_name}")
            await self.client.send_message(
                agent_name,
                "Use !vision to scan your surroundings and identify resources. "
                "Look for trees, water, caves, villages, or other useful features. "
                "Then use !findResource to locate specific things you need."
            )

            # Update tracking
            self._last_vision_time[agent_name] = now


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
