#!/usr/bin/env python3
"""
Tests for tools/evolution/agent_protocol.py

These tests ensure the AgentProtocol correctly manages agent registration
and message passing in the multi-agent network.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from tools.evolution.agent_protocol import Agent, AgentProtocol


class TestAgentDataclass:
    """Tests for Agent dataclass"""

    def test_agent_creation(self):
        """Test creating an agent"""
        agent = Agent(
            id="test-id",
            name="TestAgent",
            url="http://localhost:8000",
            capabilities=["task1", "task2"],
            weight=1.5
        )

        assert agent.id == "test-id"
        assert agent.name == "TestAgent"
        assert agent.url == "http://localhost:8000"
        assert agent.capabilities == ["task1", "task2"]
        assert agent.weight == 1.5

    def test_agent_default_weight(self):
        """Test agent with default weight"""
        agent = Agent(
            id="test-id",
            name="TestAgent",
            url=None,
            capabilities=[]
        )

        assert agent.weight == 1.0

    def test_agent_to_dict(self):
        """Test converting agent to dictionary"""
        agent = Agent(
            id="agent-123",
            name="MyAgent",
            url="http://example.com",
            capabilities=["cap1", "cap2"],
            weight=2.0
        )

        agent_dict = agent.to_dict()

        assert agent_dict == {
            'id': 'agent-123',
            'name': 'MyAgent',
            'url': 'http://example.com',
            'capabilities': ['cap1', 'cap2'],
            'weight': 2.0
        }


class TestAgentProtocolInit:
    """Tests for AgentProtocol initialization"""

    def test_initialization(self):
        """Test initializing agent protocol"""
        protocol = AgentProtocol("MainAgent")

        assert protocol.agent_name == "MainAgent"
        assert protocol.agent_id is not None
        assert isinstance(protocol.agent_id, str)
        assert protocol.network == {}

    def test_unique_agent_ids(self):
        """Test that each protocol instance gets unique ID"""
        protocol1 = AgentProtocol("Agent1")
        protocol2 = AgentProtocol("Agent2")

        assert protocol1.agent_id != protocol2.agent_id


class TestRegisterAgent:
    """Tests for agent registration"""

    def test_register_basic_agent(self):
        """Test registering a basic agent"""
        protocol = AgentProtocol("MainAgent")

        agent_id = protocol.register_agent("TestAgent")

        assert agent_id is not None
        assert isinstance(agent_id, str)
        assert agent_id in protocol.network

        agent = protocol.network[agent_id]
        assert agent.name == "TestAgent"
        assert agent.url is None
        assert agent.capabilities == []
        assert agent.weight == 1.0

    def test_register_agent_with_url(self):
        """Test registering agent with URL"""
        protocol = AgentProtocol("MainAgent")

        agent_id = protocol.register_agent("RemoteAgent", url="http://remote:8000")

        agent = protocol.network[agent_id]
        assert agent.url == "http://remote:8000"

    def test_register_agent_with_capabilities(self):
        """Test registering agent with capabilities"""
        protocol = AgentProtocol("MainAgent")

        capabilities = ["code_analysis", "testing", "deployment"]
        agent_id = protocol.register_agent("WorkerAgent", capabilities=capabilities)

        agent = protocol.network[agent_id]
        assert agent.capabilities == capabilities

    def test_register_multiple_agents(self):
        """Test registering multiple agents"""
        protocol = AgentProtocol("MainAgent")

        agent_id1 = protocol.register_agent("Agent1")
        agent_id2 = protocol.register_agent("Agent2")
        agent_id3 = protocol.register_agent("Agent3")

        assert len(protocol.network) == 3
        assert agent_id1 != agent_id2 != agent_id3


class TestFindAgent:
    """Tests for finding agents"""

    def test_find_agent_by_id(self):
        """Test finding agent by ID"""
        protocol = AgentProtocol("MainAgent")
        agent_id = protocol.register_agent("TestAgent")

        agent = protocol._find_agent(agent_id)

        assert agent is not None
        assert agent.id == agent_id
        assert agent.name == "TestAgent"

    def test_find_agent_by_name(self):
        """Test finding agent by name"""
        protocol = AgentProtocol("MainAgent")
        agent_id = protocol.register_agent("UniqueAgent")

        agent = protocol._find_agent("UniqueAgent")

        assert agent is not None
        assert agent.id == agent_id
        assert agent.name == "UniqueAgent"

    def test_find_nonexistent_agent(self):
        """Test finding agent that doesn't exist"""
        protocol = AgentProtocol("MainAgent")

        agent = protocol._find_agent("NonExistent")

        assert agent is None

    def test_find_agent_prefers_id_over_name(self):
        """Test that ID lookup is preferred over name"""
        protocol = AgentProtocol("MainAgent")

        # Register two agents, one with ID that matches another's name
        agent_id1 = protocol.register_agent("FirstAgent")
        # Manually add second agent with specific ID
        protocol.network["FirstAgent"] = Agent(
            id="FirstAgent",
            name="SecondAgent",
            url=None,
            capabilities=[]
        )

        # Should find by ID first
        agent = protocol._find_agent("FirstAgent")
        assert agent.name == "SecondAgent"


class TestSendMessage:
    """Tests for sending messages"""

    @patch.object(AgentProtocol, '_write_local_message')
    def test_send_message_to_local_agent(self, mock_write):
        """Test sending message to local agent"""
        protocol = AgentProtocol("SenderAgent")
        agent_id = protocol.register_agent("ReceiverAgent")

        payload = {"data": "test"}
        protocol.send_message("ReceiverAgent", "task", payload)

        # Should call local write
        mock_write.assert_called_once()
        call_args = mock_write.call_args[0]
        assert call_args[0] == "ReceiverAgent"

        message = call_args[1]
        assert message["from"] == "SenderAgent"
        assert message["to"] == "ReceiverAgent"
        assert message["type"] == "task"
        assert message["payload"] == payload
        assert "timestamp" in message

    @patch.object(AgentProtocol, '_send_http_message')
    def test_send_message_to_remote_agent(self, mock_http):
        """Test sending message to remote agent"""
        protocol = AgentProtocol("SenderAgent")
        agent_id = protocol.register_agent(
            "RemoteAgent",
            url="http://remote:8000"
        )

        payload = {"data": "test"}
        protocol.send_message("RemoteAgent", "task", payload)

        # Should call HTTP send
        mock_http.assert_called_once()
        url, message = mock_http.call_args[0]
        assert url == "http://remote:8000"
        assert message["from"] == "SenderAgent"
        assert message["to"] == "RemoteAgent"

    def test_send_message_includes_timestamp(self):
        """Test that messages include UTC timestamp"""
        protocol = AgentProtocol("SenderAgent")
        protocol.register_agent("ReceiverAgent")

        with patch.object(protocol, '_write_local_message') as mock_write:
            protocol.send_message("ReceiverAgent", "task", {})

            message = mock_write.call_args[0][1]
            assert "timestamp" in message
            # Verify it's a valid ISO format timestamp
            datetime.fromisoformat(message["timestamp"])

    def test_send_message_to_nonexistent_agent(self):
        """Test sending message to non-existent agent"""
        protocol = AgentProtocol("SenderAgent")

        # Should not raise exception, just do nothing
        protocol.send_message("NonExistent", "task", {})


class TestWriteLocalMessage:
    """Tests for local message writing"""

    @patch('tools.evolution.communication.local_exchange.LocalExchange')
    def test_write_local_message(self, mock_exchange_class):
        """Test writing message to local exchange"""
        mock_exchange = MagicMock()
        mock_exchange_class.return_value = mock_exchange

        protocol = AgentProtocol("SenderAgent")
        message = {
            "from": "SenderAgent",
            "to": "ReceiverAgent",
            "type": "task",
            "payload": {"data": "test"},
            "timestamp": "2025-11-07T10:00:00"
        }

        protocol._write_local_message("ReceiverAgent", message)

        mock_exchange_class.assert_called_once()
        mock_exchange.write_message.assert_called_once_with("ReceiverAgent", message)


class TestGetAgents:
    """Tests for getting all agents"""

    def test_get_agents_empty(self):
        """Test getting agents when none registered"""
        protocol = AgentProtocol("MainAgent")

        agents = protocol.get_agents()

        assert agents == []

    def test_get_agents_single(self):
        """Test getting agents with one registered"""
        protocol = AgentProtocol("MainAgent")
        agent_id = protocol.register_agent("TestAgent")

        agents = protocol.get_agents()

        assert len(agents) == 1
        assert agents[0].id == agent_id
        assert agents[0].name == "TestAgent"

    def test_get_agents_multiple(self):
        """Test getting multiple agents"""
        protocol = AgentProtocol("MainAgent")
        protocol.register_agent("Agent1")
        protocol.register_agent("Agent2")
        protocol.register_agent("Agent3")

        agents = protocol.get_agents()

        assert len(agents) == 3
        agent_names = [a.name for a in agents]
        assert "Agent1" in agent_names
        assert "Agent2" in agent_names
        assert "Agent3" in agent_names

    def test_get_agents_returns_list(self):
        """Test that get_agents returns a list"""
        protocol = AgentProtocol("MainAgent")
        protocol.register_agent("Agent1")

        agents = protocol.get_agents()

        assert isinstance(agents, list)
