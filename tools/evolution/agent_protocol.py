"""Agent Protocol for multi-agent network"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class Agent:
    """Agent in the network"""

    id: str
    name: str
    url: Optional[str]
    capabilities: List[str]
    weight: float = 1.0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "capabilities": self.capabilities,
            "weight": self.weight,
        }


class AgentProtocol:
    """Multi-agent network protocol"""

    def __init__(self, agent_name: str):
        """
        Initialize agent protocol

        Args:
            agent_name: Name of this agent
        """
        self.agent_name = agent_name
        self.agent_id = str(uuid.uuid4())
        self.network = {}  # Dict[agent_id, Agent]

    def register_agent(
        self,
        name: str,
        url: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
    ) -> str:
        """Register agent in network"""
        agent_id = str(uuid.uuid4())
        agent = Agent(
            id=agent_id, name=name, url=url, capabilities=capabilities or [], weight=1.0
        )
        self.network[agent_id] = agent
        return agent_id

    def send_message(self, target: str, message_type: str, payload: Dict):
        """
        Send message to another agent

        Args:
            target: Target agent name or ID
            message_type: Type of message
            payload: Message payload
        """
        message = {
            "from": self.agent_name,
            "to": target,
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Find agent
        agent = self._find_agent(target)

        if agent:
            if agent.url:
                # Remote agent - would use HTTP POST
                self._send_http_message(agent.url, message)
            else:
                # Local agent - use file-based exchange
                self._write_local_message(target, message)

    def _find_agent(self, target: str) -> Optional[Agent]:
        """Find agent by name or ID"""
        # Try ID first
        if target in self.network:
            return self.network[target]

        # Try name
        for agent in self.network.values():
            if agent.name == target:
                return agent

        return None

    def _send_http_message(self, url: str, message: Dict):
        """Send message via HTTP (placeholder)"""
        # Would use requests.post() in full implementation
        pass

    def _write_local_message(self, target: str, message: Dict):
        """Write message to local file exchange"""
        from .communication.local_exchange import LocalExchange

        exchange = LocalExchange()
        exchange.write_message(target, message)

    def get_agents(self) -> List[Agent]:
        """Get all registered agents"""
        return list(self.network.values())
