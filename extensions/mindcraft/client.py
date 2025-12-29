"""
Mindcraft Socket.io Client

Real-time bidirectional communication with Mindcraft MindServer.
Supports Dry Run mode for testing without a live server.

CRITICAL SAFETY RULE: All planning must avoid water blocks!
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

# Import models
from .models import AgentState, AgentStatus

# Socket.io import with fallback for dry run
try:
    import socketio

    SOCKETIO_AVAILABLE = True
except ImportError:
    socketio = None
    SOCKETIO_AVAILABLE = False


class MindcraftClient:
    """
    Socket.io client for Mindcraft MindServer communication.

    Supports:
    - Real-time agent status updates
    - Sending commands to agents
    - Agent lifecycle management
    - Dry Run mode for testing

    Usage:
        client = MindcraftClient("wss://andy.minepad.cc")
        await client.connect()
        await client.send_message("andy", "Hello!")
        status = client.get_agent_status("andy")
        await client.disconnect()
    """

    def __init__(
        self,
        server_url: str = "ws://localhost:8080",
        dry_run: bool = False,
        auto_reconnect: bool = True,
        reconnect_delay: float = 5.0,
    ):
        """
        Initialize the Mindcraft client.

        Args:
            server_url: WebSocket URL of the MindServer
            dry_run: If True, simulate operations without real connection
            auto_reconnect: Automatically reconnect on disconnect
            reconnect_delay: Seconds to wait between reconnect attempts
        """
        self.server_url = server_url
        self.dry_run = dry_run
        self.auto_reconnect = auto_reconnect
        self.reconnect_delay = reconnect_delay

        self._connected = False
        self._sio = None
        self._agents: Dict[str, AgentState] = {}
        self._callbacks: Dict[str, List[Callable]] = {
            "state_update": [],
            "agent_message": [],
            "agent_death": [],
            "human_join": [],
            "error": [],
        }
        self._message_log: List[Dict[str, Any]] = []

        # Initialize Socket.io client if available and not dry run
        if not dry_run and SOCKETIO_AVAILABLE:
            self._sio = socketio.AsyncClient(
                reconnection=auto_reconnect,
                reconnection_delay=reconnect_delay,
                logger=False,
                engineio_logger=False,
            )
            self._setup_event_handlers()

    def _setup_event_handlers(self) -> None:
        """Set up Socket.io event handlers."""
        if not self._sio:
            return

        @self._sio.event
        async def connect():
            self._connected = True
            self._log_event("connected", {"server": self.server_url})

        @self._sio.event
        async def disconnect():
            self._connected = False
            self._log_event("disconnected", {"server": self.server_url})

        @self._sio.on("agents-status")
        async def on_agents_status(data):
            self._handle_agents_status(data)

        @self._sio.on("state-update")
        async def on_state_update(data):
            self._handle_state_update(data)

        @self._sio.on("bot-output")
        async def on_bot_output(*args):
            # Server may send (agent_name, data) or just (data,)
            data = args[-1] if args else {}
            self._handle_bot_output(data)

        @self._sio.on("chat-message")
        async def on_chat_message(*args):
            # Server may send (agent_name, data) or just (data,)
            data = args[-1] if args else {}
            self._handle_chat_message(data)

    def _log_event(self, event: str, data: Any) -> None:
        """Log an event for debugging and dry run mode."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "data": data,
        }
        self._message_log.append(entry)

        # Keep only last 1000 messages
        if len(self._message_log) > 1000:
            self._message_log = self._message_log[-1000:]

    def _handle_agents_status(self, data: Any) -> None:
        """Handle agents-status event from server."""
        self._log_event("agents-status", data)

        # Server sends an array of agent objects:
        # [{name: "andy", in_game: true, viewerPort: 3000, socket_connected: true}, ...]
        if isinstance(data, list):
            for agent_info in data:
                if isinstance(agent_info, dict) and "name" in agent_info:
                    self._update_agent_from_status(agent_info["name"], agent_info)
        elif isinstance(data, dict):
            # Legacy format: {agent_name: {status...}, ...}
            for name, status in data.items():
                self._update_agent_from_status(name, status)

    def _handle_state_update(self, data: Any) -> None:
        """Handle state-update event from server."""
        self._log_event("state-update", data)

        if isinstance(data, dict) and "name" in data:
            self._update_agent_from_state(data["name"], data)

        # Notify callbacks
        for callback in self._callbacks.get("state_update", []):
            try:
                callback(data)
            except Exception as e:
                self._log_event("callback_error", {"error": str(e)})

    def _handle_bot_output(self, data: Any) -> None:
        """Handle bot-output event from server."""
        self._log_event("bot-output", data)

    def _handle_chat_message(self, data: Any) -> None:
        """Handle chat-message event from server."""
        self._log_event("chat-message", data)

        # Check for human player join
        if isinstance(data, dict):
            message = data.get("message", "")
            if "joined the game" in message.lower():
                for callback in self._callbacks.get("human_join", []):
                    try:
                        callback(data)
                    except Exception:
                        pass

    def _update_agent_from_status(self, name: str, status: Dict) -> None:
        """Update agent state from status data."""
        if name not in self._agents:
            self._agents[name] = AgentState(name=name)

        agent = self._agents[name]
        # Server sends "in_game" field to indicate if agent is online
        is_online = status.get("in_game") or status.get("online") or status.get("socket_connected")
        agent.status = AgentStatus.ONLINE if is_online else AgentStatus.OFFLINE
        agent.last_update = datetime.now()

    def _update_agent_from_state(self, name: str, state: Dict) -> None:
        """Update agent state from state update data."""
        if name not in self._agents:
            self._agents[name] = AgentState(name=name)

        agent = self._agents[name]
        previous_health = agent.health

        # Update fields
        agent.health = state.get("health", agent.health)
        agent.hunger = state.get("hunger", agent.hunger)
        if "position" in state:
            pos = state["position"]
            agent.position = (pos.get("x", 0), pos.get("y", 0), pos.get("z", 0))
        agent.biome = state.get("biome", agent.biome)
        agent.gamemode = state.get("gamemode", agent.gamemode)
        agent.inventory = state.get("inventory", agent.inventory)
        agent.current_action = state.get("action", agent.current_action)
        agent.last_message = state.get("lastMessage", agent.last_message)
        agent.last_update = datetime.now()

        # Detect death (health dropped to 0)
        if previous_health > 0 and agent.health <= 0:
            for callback in self._callbacks.get("agent_death", []):
                try:
                    callback({"agent": name, "state": agent.to_dict()})
                except Exception:
                    pass

    # ==================== Connection Methods ====================

    async def connect(self) -> bool:
        """
        Connect to the MindServer.

        Returns:
            True if connected successfully (or dry run), False otherwise
        """
        if self.dry_run:
            self._connected = True
            self._log_event("dry_run_connect", {"server": self.server_url})
            # Initialize mock agents in dry run mode
            self._agents["andy"] = AgentState(
                name="andy",
                status=AgentStatus.ONLINE,
                health=20.0,
                hunger=18.0,
                position=(100, 64, 100),
                biome="plains",
            )
            return True

        if not SOCKETIO_AVAILABLE:
            self._log_event("error", {"message": "python-socketio not installed"})
            return False

        try:
            await self._sio.connect(self.server_url)
            self._connected = True
            return True
        except Exception as e:
            self._log_event("connect_error", {"error": str(e)})
            return False

    async def disconnect(self) -> None:
        """Disconnect from the MindServer."""
        if self.dry_run:
            self._connected = False
            self._log_event("dry_run_disconnect", {})
            return

        if self._sio and self._connected:
            await self._sio.disconnect()

        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected

    # ==================== Agent Control Methods ====================

    async def send_message(self, agent_name: str, message: str) -> bool:
        """
        Send a message/command to an agent.

        Args:
            agent_name: Name of the agent (e.g., "andy")
            message: Message or command to send

        Returns:
            True if sent successfully
        """
        if self.dry_run:
            self._log_event(
                "dry_run_send_message", {"agent": agent_name, "message": message}
            )
            return True

        if not self._connected:
            return False

        try:
            # Server expects: socket.on('send-message', (agentName, data) => ...)
            # Agent expects data to have: { from: senderName, message: content }
            # python-socketio requires a tuple to send multiple arguments
            await self._sio.emit(
                "send-message", (agent_name, {"from": "Orchestrator", "message": message})
            )
            self._log_event("send_message", {"agent": agent_name, "message": message})
            return True
        except Exception as e:
            self._log_event("send_error", {"error": str(e)})
            return False

    async def start_agent(self, agent_name: str) -> bool:
        """Start an agent."""
        if self.dry_run:
            self._log_event("dry_run_start_agent", {"agent": agent_name})
            if agent_name in self._agents:
                self._agents[agent_name].status = AgentStatus.ONLINE
            return True

        if not self._connected:
            return False

        try:
            await self._sio.emit("start-agent", {"agentName": agent_name})
            return True
        except Exception as e:
            self._log_event("error", {"error": str(e)})
            return False

    async def stop_agent(self, agent_name: str) -> bool:
        """Stop an agent."""
        if self.dry_run:
            self._log_event("dry_run_stop_agent", {"agent": agent_name})
            if agent_name in self._agents:
                self._agents[agent_name].status = AgentStatus.OFFLINE
            return True

        if not self._connected:
            return False

        try:
            await self._sio.emit("stop-agent", {"agentName": agent_name})
            return True
        except Exception as e:
            self._log_event("error", {"error": str(e)})
            return False

    async def restart_agent(self, agent_name: str) -> bool:
        """Restart an agent."""
        if self.dry_run:
            self._log_event("dry_run_restart_agent", {"agent": agent_name})
            return True

        if not self._connected:
            return False

        try:
            await self._sio.emit("restart-agent", {"agentName": agent_name})
            return True
        except Exception as e:
            self._log_event("error", {"error": str(e)})
            return False

    # ==================== State Query Methods ====================

    def get_agent_status(self, agent_name: str) -> Optional[AgentState]:
        """
        Get the current status of an agent.

        Args:
            agent_name: Name of the agent

        Returns:
            AgentState if known, None otherwise
        """
        return self._agents.get(agent_name)

    def get_all_agents(self) -> Dict[str, AgentState]:
        """Get status of all known agents."""
        return self._agents.copy()

    def get_agent_names(self) -> List[str]:
        """Get list of known agent names."""
        return list(self._agents.keys())

    # ==================== Callback Registration ====================

    def on_state_update(self, callback: Callable[[Dict], None]) -> None:
        """Register callback for state updates."""
        self._callbacks["state_update"].append(callback)

    def on_agent_death(self, callback: Callable[[Dict], None]) -> None:
        """Register callback for agent deaths."""
        self._callbacks["agent_death"].append(callback)

    def on_human_join(self, callback: Callable[[Dict], None]) -> None:
        """Register callback for human player joins."""
        self._callbacks["human_join"].append(callback)

    def on_error(self, callback: Callable[[Dict], None]) -> None:
        """Register callback for errors."""
        self._callbacks["error"].append(callback)

    # ==================== Utility Methods ====================

    def get_message_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent message log entries."""
        return self._message_log[-limit:]

    def clear_message_log(self) -> None:
        """Clear the message log."""
        self._message_log.clear()

    async def wait_for_agent(
        self, agent_name: str, timeout: float = 30.0
    ) -> Optional[AgentState]:
        """
        Wait for an agent to come online.

        Args:
            agent_name: Name of the agent to wait for
            timeout: Maximum seconds to wait

        Returns:
            AgentState if agent comes online, None if timeout
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            agent = self.get_agent_status(agent_name)
            if agent and agent.status == AgentStatus.ONLINE:
                return agent
            await asyncio.sleep(0.5)
        return None


# ==================== Synchronous Wrapper ====================


class MindcraftClientSync:
    """
    Synchronous wrapper for MindcraftClient.

    For use in non-async contexts (e.g., CLI tools).
    """

    def __init__(self, *args, **kwargs):
        self._async_client = MindcraftClient(*args, **kwargs)
        self._loop = None

    def _get_loop(self):
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def connect(self) -> bool:
        return self._get_loop().run_until_complete(self._async_client.connect())

    def disconnect(self) -> None:
        self._get_loop().run_until_complete(self._async_client.disconnect())

    def send_message(self, agent_name: str, message: str) -> bool:
        return self._get_loop().run_until_complete(
            self._async_client.send_message(agent_name, message)
        )

    def start_agent(self, agent_name: str) -> bool:
        return self._get_loop().run_until_complete(
            self._async_client.start_agent(agent_name)
        )

    def stop_agent(self, agent_name: str) -> bool:
        return self._get_loop().run_until_complete(
            self._async_client.stop_agent(agent_name)
        )

    def restart_agent(self, agent_name: str) -> bool:
        return self._get_loop().run_until_complete(
            self._async_client.restart_agent(agent_name)
        )

    def get_agent_status(self, agent_name: str) -> Optional[AgentState]:
        return self._async_client.get_agent_status(agent_name)

    def get_all_agents(self) -> Dict[str, AgentState]:
        return self._async_client.get_all_agents()

    @property
    def is_connected(self) -> bool:
        return self._async_client.is_connected

    @property
    def dry_run(self) -> bool:
        return self._async_client.dry_run


if __name__ == "__main__":
    # Self-test with dry run
    print("Mindcraft Client Self-Test (Dry Run Mode)")
    print("=" * 50)

    client = MindcraftClientSync(
        server_url="wss://andy.minepad.cc",
        dry_run=True,
    )

    print(f"Dry Run Mode: {client.dry_run}")
    print("Connecting...")

    if client.connect():
        print("Connected!")
        print(f"Is Connected: {client.is_connected}")

        agents = client.get_all_agents()
        print(f"\nKnown Agents: {list(agents.keys())}")

        for name, state in agents.items():
            print(f"\n{name}:")
            print(f"  Status: {state.status.value}")
            print(f"  Health: {state.health}")
            print(f"  Position: {state.position}")

        print("\nSending test message...")
        client.send_message("andy", "Hello from Context Foundry!")

        print("\nDisconnecting...")
        client.disconnect()
        print(f"Is Connected: {client.is_connected}")
    else:
        print("Failed to connect!")
