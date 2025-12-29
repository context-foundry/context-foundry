"""
Mindcraft State Monitor

Tracks world state, agent health, and detects anomalies.
"""

import asyncio
from typing import Dict, Optional
from datetime import datetime

from .client import MindcraftClient
from .models import AgentStatus
from .persistence import MindcraftPersistence


class MindcraftMonitor:
    """
    Monitors Mindcraft agents and world state.

    Responsibilities:
    1. Listen to state updates from client
    2. Persist state changes to disk
    3. Detect anomalies (death, stuck, disconnects)
    4. Provide current state to other components
    """

    def __init__(
        self,
        client: MindcraftClient,
        persistence: Optional[MindcraftPersistence] = None,
        check_interval: float = 1.0,
    ):
        """
        Initialize the monitor.

        Args:
            client: MindcraftClient instance
            persistence: Persistence manager (creates default if None)
            check_interval: Interval for anomaly detection checks
        """
        self.client = client
        self.persistence = persistence or MindcraftPersistence()
        self.check_interval = check_interval

        self._running = False
        self._monitor_task = None
        self._agent_last_positions: Dict[str, tuple] = {}
        self._agent_stuck_counts: Dict[str, int] = {}

        # Anomaly detection thresholds
        self.STUCK_THRESHOLD = 5  # Number of checks with no movement to consider stuck
        self.TIMEOUT_THRESHOLD = 60.0  # Seconds without update to consider offline

        # Register callbacks
        self.client.on_state_update(self._on_state_update)
        self.client.on_agent_death(self._on_agent_death)

    async def start(self):
        """Start the monitoring loop."""
        if self._running:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        print("Mindcraft Monitor started")

    async def stop(self):
        """Stop the monitoring loop."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        print("Mindcraft Monitor stopped")

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                self._check_timeouts()
                self._check_stuck_agents()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                print(f"Error in monitor loop: {e}")
                await asyncio.sleep(1.0)

    def _on_state_update(self, data: Dict):
        """Handle incoming state update from client."""
        # Client already updates its internal models.
        # We just need to persist the updated state.
        name = data.get("name")
        if name:
            agent_state = self.client.get_agent_status(name)
            if agent_state:
                self.persistence.save_agent_state(agent_state)

    def _on_agent_death(self, data: Dict):
        """Handle agent death event."""
        agent_name = data.get("agent")
        state_dict = data.get("state", {})

        print(f"💀 DETECTED AGENT DEATH: {agent_name}")

        # Log to history
        self.persistence.save_history(
            "death",
            {
                "agent": agent_name,
                "location": state_dict.get("position"),
                "time": datetime.now().isoformat(),
            },
        )

    def _check_timeouts(self):
        """Check for agents that haven't sent updates recently."""
        now = datetime.now()
        agents = self.client.get_all_agents()

        for name, agent in agents.items():
            if agent.status == AgentStatus.ONLINE:
                time_since_last = (now - agent.last_update).total_seconds()
                if time_since_last > self.TIMEOUT_THRESHOLD:
                    print(f"⚠️ Agent {name} timed out ({time_since_last:.1f}s ago)")
                    # We don't change status locally, just warn
                    # The connection status is handled by socket.io events

    def _check_stuck_agents(self):
        """Check for agents that might be stuck (not moving while active)."""
        agents = self.client.get_all_agents()

        for name, agent in agents.items():
            # Skip if not online or "idle" action
            if agent.status != AgentStatus.ONLINE:
                continue

            # If agent is supposedly moving but position hasn't changed
            current_pos = agent.position
            last_pos = self._agent_last_positions.get(name)

            if last_pos == current_pos:
                self._agent_stuck_counts[name] = (
                    self._agent_stuck_counts.get(name, 0) + 1
                )
            else:
                self._agent_stuck_counts[name] = 0
                self._agent_last_positions[name] = current_pos

            # Log stuck warning (but don't spam)
            if self._agent_stuck_counts[name] == self.STUCK_THRESHOLD:
                print(
                    f"⚠️ Agent {name} appears stationary for {self.STUCK_THRESHOLD} checks"
                )
                self.persistence.save_history(
                    "stuck_warning",
                    {
                        "agent": name,
                        "position": list(current_pos),
                        "duration_checks": self.STUCK_THRESHOLD,
                    },
                )

    def get_monitor_status(self) -> Dict:
        """Get internal status of the monitor."""
        return {
            "running": self._running,
            "tracked_agents": list(self.client.get_agent_names()),
            "stuck_counts": self._agent_stuck_counts,
        }
