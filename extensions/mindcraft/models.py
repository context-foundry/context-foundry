"""
Mindcraft Data Models

Core data structures for Mindcraft state, status, and configuration.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List


class AgentStatus(Enum):
    """Agent connection status."""

    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    STARTING = "starting"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class InventoryItem:
    """Represents an item in the agent's inventory."""

    name: str
    count: int
    slot: int
    # Add other item properties as needed (durability, enchantments)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "count": self.count, "slot": self.slot}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InventoryItem":
        return cls(
            name=data.get("name", "air"),
            count=data.get("count", 0),
            slot=data.get("slot", 0),
        )


@dataclass
class AgentState:
    """Current state of a Mindcraft agent."""

    name: str
    status: AgentStatus = AgentStatus.UNKNOWN
    health: float = 20.0
    hunger: float = 20.0
    position: tuple = (0.0, 0.0, 0.0)
    biome: str = "unknown"
    gamemode: str = "survival"
    inventory: List[Dict[str, Any]] = field(default_factory=list)
    equipped: List[str] = field(default_factory=list)
    current_action: str = ""
    last_message: str = ""
    last_update: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "health": self.health,
            "hunger": self.hunger,
            "position": list(self.position),
            "biome": self.biome,
            "gamemode": self.gamemode,
            "inventory": self.inventory,
            "equipped": self.equipped,
            "current_action": self.current_action,
            "last_message": self.last_message,
            "last_update": self.last_update.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentState":
        """Create AgentState from dictionary."""
        # Parse status enum
        status_val = data.get("status", "unknown")
        try:
            status = AgentStatus(status_val)
        except ValueError:
            status = AgentStatus.UNKNOWN

        # Parse position tuple
        pos_list = data.get("position", [0, 0, 0])
        position = tuple(pos_list) if isinstance(pos_list, list) else (0, 0, 0)

        # Parse timestamp
        last_update_str = data.get("last_update")
        if last_update_str:
            try:
                last_update = datetime.fromisoformat(last_update_str)
            except ValueError:
                last_update = datetime.now()
        else:
            last_update = datetime.now()

        return cls(
            name=data.get("name", "unknown"),
            status=status,
            health=float(data.get("health", 20.0)),
            hunger=float(data.get("hunger", 20.0)),
            position=position,
            biome=data.get("biome", "unknown"),
            gamemode=data.get("gamemode", "survival"),
            inventory=data.get("inventory", []),
            equipped=data.get("equipped", []),
            current_action=data.get("current_action", ""),
            last_message=data.get("last_message", ""),
            last_update=last_update,
        )
