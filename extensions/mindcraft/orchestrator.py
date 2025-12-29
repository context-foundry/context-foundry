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
        print("💓 Main loop active")

        while self._running:
            try:
                # 1. Update Planner (Strategize)
                # This checks goals, assigns tasks, and may trigger LLM
                self.planner.update()

                # 2. Sleep tick
                # Detailed work happens in background tasks (monitor, etc)
                await asyncio.sleep(1.0)

            except Exception as e:
                print(f"⚠️ Error in main loop: {e}")
                await asyncio.sleep(1.0)


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
