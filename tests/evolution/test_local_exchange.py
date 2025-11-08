#!/usr/bin/env python3
"""
Tests for tools/evolution/communication/local_exchange.py

These tests ensure the LocalExchange correctly manages file-based
message passing between agents.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from tools.evolution.communication.local_exchange import LocalExchange


class TestLocalExchangeInit:
    """Tests for LocalExchange initialization"""

    def test_initialization(self, tmp_path):
        """Test that LocalExchange creates shared directory"""
        with patch('tools.evolution.communication.local_exchange.Path.home') as mock_home:
            mock_home.return_value = tmp_path

            exchange = LocalExchange()

            expected_dir = tmp_path / ".context-foundry" / "evolution" / "shared_tasks"
            assert exchange.shared_dir == expected_dir
            assert expected_dir.exists()

    def test_shared_dir_already_exists(self, tmp_path):
        """Test initialization when shared directory already exists"""
        with patch('tools.evolution.communication.local_exchange.Path.home') as mock_home:
            mock_home.return_value = tmp_path

            # Create directory beforehand
            shared_dir = tmp_path / ".context-foundry" / "evolution" / "shared_tasks"
            shared_dir.mkdir(parents=True, exist_ok=True)

            # Should not raise error
            exchange = LocalExchange()
            assert exchange.shared_dir.exists()


class TestWriteMessage:
    """Tests for writing messages"""

    def test_write_message(self, tmp_path):
        """Test writing a message to shared directory"""
        with patch('tools.evolution.communication.local_exchange.Path.home') as mock_home:
            mock_home.return_value = tmp_path

            exchange = LocalExchange()

            message = {
                "from": "AgentA",
                "to": "AgentB",
                "type": "task",
                "payload": {"data": "test"},
                "timestamp": "2025-11-07T10:00:00.123456"
            }

            exchange.write_message("AgentB", message)

            # Check file was created
            expected_file = exchange.shared_dir / "msg_AgentB_2025-11-07T10:00:00.123456.json"
            assert expected_file.exists()

            # Check content
            with open(expected_file) as f:
                saved_message = json.load(f)

            assert saved_message == message

    def test_write_multiple_messages(self, tmp_path):
        """Test writing multiple messages"""
        with patch('tools.evolution.communication.local_exchange.Path.home') as mock_home:
            mock_home.return_value = tmp_path

            exchange = LocalExchange()

            message1 = {
                "from": "AgentA",
                "to": "AgentB",
                "type": "task",
                "payload": {"data": "test1"},
                "timestamp": "2025-11-07T10:00:00.000001"
            }

            message2 = {
                "from": "AgentA",
                "to": "AgentB",
                "type": "task",
                "payload": {"data": "test2"},
                "timestamp": "2025-11-07T10:00:00.000002"
            }

            exchange.write_message("AgentB", message1)
            exchange.write_message("AgentB", message2)

            # Check both files exist
            files = list(exchange.shared_dir.glob("msg_AgentB_*.json"))
            assert len(files) == 2

    def test_write_message_different_agents(self, tmp_path):
        """Test writing messages to different agents"""
        with patch('tools.evolution.communication.local_exchange.Path.home') as mock_home:
            mock_home.return_value = tmp_path

            exchange = LocalExchange()

            message1 = {
                "from": "AgentA",
                "to": "AgentB",
                "type": "task",
                "payload": {"data": "for B"},
                "timestamp": "2025-11-07T10:00:00.000001"
            }

            message2 = {
                "from": "AgentA",
                "to": "AgentC",
                "type": "task",
                "payload": {"data": "for C"},
                "timestamp": "2025-11-07T10:00:00.000002"
            }

            exchange.write_message("AgentB", message1)
            exchange.write_message("AgentC", message2)

            # Check files exist for both agents
            b_files = list(exchange.shared_dir.glob("msg_AgentB_*.json"))
            c_files = list(exchange.shared_dir.glob("msg_AgentC_*.json"))

            assert len(b_files) == 1
            assert len(c_files) == 1


class TestReadMessages:
    """Tests for reading messages"""

    def test_read_messages_empty(self, tmp_path):
        """Test reading messages when none exist"""
        with patch('tools.evolution.communication.local_exchange.Path.home') as mock_home:
            mock_home.return_value = tmp_path

            exchange = LocalExchange()

            messages = exchange.read_messages("AgentB")

            assert messages == []

    def test_read_single_message(self, tmp_path):
        """Test reading a single message"""
        with patch('tools.evolution.communication.local_exchange.Path.home') as mock_home:
            mock_home.return_value = tmp_path

            exchange = LocalExchange()

            message = {
                "from": "AgentA",
                "to": "AgentB",
                "type": "task",
                "payload": {"data": "test"},
                "timestamp": "2025-11-07T10:00:00.123456"
            }

            exchange.write_message("AgentB", message)

            messages = exchange.read_messages("AgentB")

            assert len(messages) == 1
            assert messages[0] == message

    def test_read_multiple_messages(self, tmp_path):
        """Test reading multiple messages"""
        with patch('tools.evolution.communication.local_exchange.Path.home') as mock_home:
            mock_home.return_value = tmp_path

            exchange = LocalExchange()

            message1 = {
                "from": "AgentA",
                "to": "AgentB",
                "type": "task",
                "payload": {"data": "test1"},
                "timestamp": "2025-11-07T10:00:00.000001"
            }

            message2 = {
                "from": "AgentC",
                "to": "AgentB",
                "type": "task",
                "payload": {"data": "test2"},
                "timestamp": "2025-11-07T10:00:00.000002"
            }

            exchange.write_message("AgentB", message1)
            exchange.write_message("AgentB", message2)

            messages = exchange.read_messages("AgentB")

            assert len(messages) == 2
            # Messages should contain both (order may vary)
            payloads = [m["payload"]["data"] for m in messages]
            assert "test1" in payloads
            assert "test2" in payloads

    def test_read_messages_deletes_files(self, tmp_path):
        """Test that reading messages deletes the files"""
        with patch('tools.evolution.communication.local_exchange.Path.home') as mock_home:
            mock_home.return_value = tmp_path

            exchange = LocalExchange()

            message = {
                "from": "AgentA",
                "to": "AgentB",
                "type": "task",
                "payload": {"data": "test"},
                "timestamp": "2025-11-07T10:00:00.123456"
            }

            exchange.write_message("AgentB", message)

            # Verify file exists
            files_before = list(exchange.shared_dir.glob("msg_AgentB_*.json"))
            assert len(files_before) == 1

            # Read messages
            exchange.read_messages("AgentB")

            # Verify file was deleted
            files_after = list(exchange.shared_dir.glob("msg_AgentB_*.json"))
            assert len(files_after) == 0

    def test_read_messages_only_for_agent(self, tmp_path):
        """Test that reading only returns messages for specific agent"""
        with patch('tools.evolution.communication.local_exchange.Path.home') as mock_home:
            mock_home.return_value = tmp_path

            exchange = LocalExchange()

            message_b = {
                "from": "AgentA",
                "to": "AgentB",
                "type": "task",
                "payload": {"data": "for B"},
                "timestamp": "2025-11-07T10:00:00.000001"
            }

            message_c = {
                "from": "AgentA",
                "to": "AgentC",
                "type": "task",
                "payload": {"data": "for C"},
                "timestamp": "2025-11-07T10:00:00.000002"
            }

            exchange.write_message("AgentB", message_b)
            exchange.write_message("AgentC", message_c)

            # Read messages for AgentB
            messages = exchange.read_messages("AgentB")

            # Should only get AgentB's message
            assert len(messages) == 1
            assert messages[0]["to"] == "AgentB"

            # AgentC's message should still exist
            c_files = list(exchange.shared_dir.glob("msg_AgentC_*.json"))
            assert len(c_files) == 1

    def test_read_messages_twice_returns_empty(self, tmp_path):
        """Test that reading messages twice returns empty on second read"""
        with patch('tools.evolution.communication.local_exchange.Path.home') as mock_home:
            mock_home.return_value = tmp_path

            exchange = LocalExchange()

            message = {
                "from": "AgentA",
                "to": "AgentB",
                "type": "task",
                "payload": {"data": "test"},
                "timestamp": "2025-11-07T10:00:00.123456"
            }

            exchange.write_message("AgentB", message)

            # First read
            messages1 = exchange.read_messages("AgentB")
            assert len(messages1) == 1

            # Second read should be empty
            messages2 = exchange.read_messages("AgentB")
            assert len(messages2) == 0


class TestIntegration:
    """Integration tests for message exchange"""

    def test_full_message_flow(self, tmp_path):
        """Test complete message exchange flow"""
        with patch('tools.evolution.communication.local_exchange.Path.home') as mock_home:
            mock_home.return_value = tmp_path

            exchange = LocalExchange()

            # Agent A sends message to Agent B
            message = {
                "from": "AgentA",
                "to": "AgentB",
                "type": "request",
                "payload": {"task": "analyze_code", "file": "main.py"},
                "timestamp": "2025-11-07T10:00:00.123456"
            }

            exchange.write_message("AgentB", message)

            # Agent B reads the message
            messages = exchange.read_messages("AgentB")

            assert len(messages) == 1
            assert messages[0]["from"] == "AgentA"
            assert messages[0]["payload"]["task"] == "analyze_code"

            # Message should be deleted after reading
            remaining_messages = exchange.read_messages("AgentB")
            assert len(remaining_messages) == 0
