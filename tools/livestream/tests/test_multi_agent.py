"""
Tests for multi-agent monitoring features
"""
import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from metrics_db import MetricsDatabase


class TestAgentInstances:
    """Test agent instance tracking functionality."""

    def setup_method(self):
        """Set up test database."""
        # Use temporary file instead of :memory: since we need persistent connection
        self.tmp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.tmp_db.close()
        self.db = MetricsDatabase(db_path=self.tmp_db.name)

    def teardown_method(self):
        """Clean up test database."""
        if hasattr(self, 'tmp_db') and os.path.exists(self.tmp_db.name):
            os.unlink(self.tmp_db.name)

    def test_create_agent_instance(self):
        """Test creating an agent instance."""
        agent_data = {
            'session_id': 'test-session',
            'agent_id': 'scout-001',
            'agent_type': 'Scout',
            'agent_name': 'Scout',
            'status': 'active',
            'phase': 'Research',
            'progress_percent': 50.0,
            'tokens_used': 10000,
            'tokens_limit': 200000,
            'token_percentage': 5.0
        }

        agent_id = self.db.create_agent_instance(agent_data)
        assert agent_id == 'scout-001'

        # Verify it was created
        agent = self.db.get_agent_instance('scout-001')
        assert agent is not None
        assert agent['agent_type'] == 'Scout'
        assert agent['status'] == 'active'
        assert agent['progress_percent'] == 50.0

    def test_update_agent_instance(self):
        """Test updating an agent instance."""
        # Create agent
        agent_data = {
            'session_id': 'test-session',
            'agent_id': 'builder-001',
            'agent_type': 'Builder',
            'status': 'active',
            'progress_percent': 25.0
        }
        self.db.create_agent_instance(agent_data)

        # Update progress
        self.db.update_agent_instance('builder-001', {
            'progress_percent': 75.0,
            'tokens_used': 50000,
            'status': 'active'
        })

        # Verify update
        agent = self.db.get_agent_instance('builder-001')
        assert agent['progress_percent'] == 75.0
        assert agent['tokens_used'] == 50000

    def test_get_session_agents(self):
        """Test getting all agents for a session."""
        # Create multiple agents
        agents_data = [
            {'session_id': 'test-session', 'agent_id': 'scout-001', 'agent_type': 'Scout'},
            {'session_id': 'test-session', 'agent_id': 'architect-001', 'agent_type': 'Architect'},
            {'session_id': 'other-session', 'agent_id': 'builder-001', 'agent_type': 'Builder'}
        ]

        for agent_data in agents_data:
            self.db.create_agent_instance(agent_data)

        # Get agents for test-session
        agents = self.db.get_session_agents('test-session')
        assert len(agents) == 2
        agent_types = [a['agent_type'] for a in agents]
        assert 'Scout' in agent_types
        assert 'Architect' in agent_types
        assert 'Builder' not in agent_types

    def test_get_active_agents(self):
        """Test getting active agents."""
        # Create agents with different statuses
        agents_data = [
            {'session_id': 'test-session', 'agent_id': 'scout-001', 'agent_type': 'Scout', 'status': 'active'},
            {'session_id': 'test-session', 'agent_id': 'architect-001', 'agent_type': 'Architect', 'status': 'completed'},
            {'session_id': 'test-session', 'agent_id': 'builder-001', 'agent_type': 'Builder', 'status': 'idle'}
        ]

        for agent_data in agents_data:
            self.db.create_agent_instance(agent_data)

        # Get active agents
        active = self.db.get_active_agents('test-session')
        assert len(active) == 2  # active and idle, not completed
        statuses = [a['status'] for a in active]
        assert 'active' in statuses
        assert 'idle' in statuses
        assert 'completed' not in statuses

    def test_get_all_instances(self):
        """Test getting all instances with stats."""
        # Create task
        self.db.create_task({
            'task_id': 'test-session',
            'project_name': 'test-project',
            'status': 'running',
            'current_phase': 'Builder'
        })

        # Create agents
        agents_data = [
            {'session_id': 'test-session', 'agent_id': 'scout-001', 'agent_type': 'Scout', 'status': 'completed'},
            {'session_id': 'test-session', 'agent_id': 'builder-001', 'agent_type': 'Builder', 'status': 'active'}
        ]

        for agent_data in agents_data:
            self.db.create_agent_instance(agent_data)

        # Get instances
        instances = self.db.get_all_instances()
        assert len(instances) > 0

        test_instance = [i for i in instances if i['session_id'] == 'test-session'][0]
        assert test_instance['project_name'] == 'test-project'
        assert test_instance['agents_total'] == 2
        assert test_instance['agents_active'] == 1  # Only Builder is active


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
