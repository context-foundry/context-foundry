#!/usr/bin/env python3
"""
Pytest configuration and shared fixtures for Context Foundry tests.

This module provides reusable fixtures for testing across all modules.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock
from typing import Dict, Any
from datetime import datetime

import pytest

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ace.providers.base_provider import Model, ModelPricing, ProviderResponse
from ace.context_manager import ContextMetrics, ContentItem


# ============================================================================
# ENVIRONMENT FIXTURES
# ============================================================================

@pytest.fixture
def clean_env(monkeypatch):
    """Provide a clean environment with test API keys."""
    test_env = {
        'ANTHROPIC_API_KEY': 'test-anthropic-key-12345',
        'OPENAI_API_KEY': 'test-openai-key-12345',
        'GITHUB_TOKEN': 'test-github-token-12345',
        'ZAI_API_KEY': 'test-zai-key-12345',
        'BUILDER_PROVIDER': 'anthropic',
        'BUILDER_MODEL': 'claude-3-5-sonnet-20241022',
        'SCOUT_PROVIDER': 'anthropic',
        'SCOUT_MODEL': 'claude-3-5-haiku-20241022',
        'ARCHITECT_PROVIDER': 'anthropic',
        'ARCHITECT_MODEL': 'claude-3-5-sonnet-20241022',
    }

    for key, value in test_env.items():
        monkeypatch.setenv(key, value)

    return test_env


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory structure."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create common directories
    (project_dir / "src").mkdir()
    (project_dir / "tests").mkdir()
    (project_dir / ".context-foundry").mkdir()

    return project_dir


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture
def in_memory_db(tmp_path):
    """Provide an in-memory SQLite database path."""
    db_path = tmp_path / "test.db"
    return str(db_path)


# ============================================================================
# MODEL AND PRICING FIXTURES
# ============================================================================

@pytest.fixture
def sample_model():
    """Provide a sample Model instance for testing."""
    return Model(
        name="claude-3-5-sonnet-20241022",
        display_name="Claude 3.5 Sonnet",
        context_window=200000,
        description="Most intelligent model for complex tasks"
    )


@pytest.fixture
def sample_models():
    """Provide multiple sample models."""
    return [
        Model(
            name="claude-3-5-sonnet-20241022",
            display_name="Claude 3.5 Sonnet",
            context_window=200000,
            description="Most intelligent model"
        ),
        Model(
            name="claude-3-5-haiku-20241022",
            display_name="Claude 3.5 Haiku",
            context_window=200000,
            description="Fastest model"
        ),
    ]


@pytest.fixture
def sample_pricing():
    """Provide sample ModelPricing instance."""
    return ModelPricing(
        model="claude-3-5-sonnet-20241022",
        input_cost_per_1m=3.00,
        output_cost_per_1m=15.00,
        context_window=200000,
        updated_at=datetime.now()
    )


@pytest.fixture
def sample_pricing_dict():
    """Provide sample pricing dictionary for multiple models."""
    return {
        "claude-3-5-sonnet-20241022": ModelPricing(
            model="claude-3-5-sonnet-20241022",
            input_cost_per_1m=3.00,
            output_cost_per_1m=15.00,
            context_window=200000,
            updated_at=datetime.now()
        ),
        "claude-3-5-haiku-20241022": ModelPricing(
            model="claude-3-5-haiku-20241022",
            input_cost_per_1m=1.00,
            output_cost_per_1m=5.00,
            context_window=200000,
            updated_at=datetime.now()
        ),
    }


@pytest.fixture
def sample_provider_response():
    """Provide sample ProviderResponse."""
    return ProviderResponse(
        content="This is a test response from the model.",
        input_tokens=100,
        output_tokens=50,
        thinking_tokens=0
    )


# ============================================================================
# CONTEXT MANAGER FIXTURES
# ============================================================================

@pytest.fixture
def sample_content_item():
    """Provide a sample ContentItem."""
    return ContentItem(
        role="user",
        content="This is a test message with code and specifications.",
        tokens=50,
        timestamp="2024-01-01T12:00:00",
        content_type="message",
        importance=0.75
    )


@pytest.fixture
def sample_content_items():
    """Provide multiple sample ContentItems."""
    return [
        ContentItem(
            role="user",
            content="Initial project requirements and specifications.",
            tokens=100,
            timestamp="2024-01-01T12:00:00",
            content_type="message",
            importance=0.9
        ),
        ContentItem(
            role="assistant",
            content="I understand. Let me analyze the requirements.",
            tokens=20,
            timestamp="2024-01-01T12:01:00",
            content_type="message",
            importance=0.5
        ),
        ContentItem(
            role="user",
            content="Here's some additional context about the project.",
            tokens=80,
            timestamp="2024-01-01T12:05:00",
            content_type="message",
            importance=0.7
        ),
    ]


@pytest.fixture
def sample_context_metrics():
    """Provide sample ContextMetrics."""
    return ContextMetrics(
        total_tokens=5000,
        max_tokens=200000,
        usage_percentage=2.5,
        num_items=10,
        compactions=0
    )


# ============================================================================
# MOCK PROVIDER FIXTURES
# ============================================================================

@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic API client."""
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Test response from Claude")]
    mock_message.usage = MagicMock(
        input_tokens=100,
        output_tokens=50
    )
    mock_client.messages.create.return_value = mock_message
    return mock_client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI API client."""
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Test response from GPT"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = MagicMock(
        prompt_tokens=100,
        completion_tokens=50
    )
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


# ============================================================================
# FILE SYSTEM FIXTURES
# ============================================================================

@pytest.fixture
def sample_python_file(tmp_path):
    """Create a sample Python file for testing."""
    file_path = tmp_path / "sample.py"
    content = '''
"""Sample Python module for testing."""

def add(a, b):
    """Add two numbers."""
    return a + b

class Calculator:
    """Simple calculator class."""

    def multiply(self, a, b):
        """Multiply two numbers."""
        return a * b
'''
    file_path.write_text(content)
    return file_path


@pytest.fixture
def sample_test_file(tmp_path):
    """Create a sample test file."""
    file_path = tmp_path / "test_sample.py"
    content = '''
"""Tests for sample module."""

def test_add():
    """Test addition."""
    assert add(2, 3) == 5

def test_multiply():
    """Test multiplication."""
    calc = Calculator()
    assert calc.multiply(2, 3) == 6
'''
    file_path.write_text(content)
    return file_path


# ============================================================================
# CHECKPOINT FIXTURES
# ============================================================================

@pytest.fixture
def sample_checkpoint_data():
    """Provide sample checkpoint data."""
    return {
        'phase': 'planning',
        'status': 'complete',
        'timestamp': '2024-01-01T12:00:00',
        'data': {
            'plan': 'Test plan data',
            'subagents': [
                {'name': 'scout1', 'status': 'pending'},
                {'name': 'builder1', 'status': 'pending'}
            ]
        }
    }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def assert_valid_cost(cost: float, min_val: float = 0.0, max_val: float = 1000.0):
    """Assert that a cost value is valid and within reasonable bounds."""
    assert isinstance(cost, (int, float)), f"Cost must be numeric, got {type(cost)}"
    assert cost >= min_val, f"Cost {cost} is below minimum {min_val}"
    assert cost <= max_val, f"Cost {cost} exceeds maximum {max_val}"


def assert_valid_percentage(percentage: float, min_val: float = 0.0, max_val: float = 100.0):
    """Assert that a percentage is valid."""
    assert isinstance(percentage, (int, float)), f"Percentage must be numeric"
    assert min_val <= percentage <= max_val, f"Percentage {percentage} out of range [{min_val}, {max_val}]"


# Make utility functions available to all tests
pytest.assert_valid_cost = assert_valid_cost
pytest.assert_valid_percentage = assert_valid_percentage
