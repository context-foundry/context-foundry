"""Pytest configuration and fixtures."""

import os
from pathlib import Path

import pytest


@pytest.fixture
def test_config():
    """Provide test configuration."""
    return {
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", "test_key"),
        "run_integration_tests": os.getenv("RUN_INTEGRATION_TESTS", "false").lower() == "true",
    }


@pytest.fixture
def sample_document():
    """Provide path to sample document."""
    return Path(__file__).parent.parent.parent / "test_data" / "sample.pdf"


@pytest.fixture
def sample_dataset():
    """Provide path to sample dataset."""
    return Path(__file__).parent.parent.parent / "test_data" / "sample.csv"


@pytest.fixture
def sample_questions():
    """Provide sample questions for document analysis."""
    return [
        "What is the main topic?",
        "What are the key findings?",
        "What recommendations are provided?",
    ]
