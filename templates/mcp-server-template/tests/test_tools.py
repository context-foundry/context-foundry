"""
Tests for MCP server tools

Run with: python3 -m pytest tests/
"""

import json
import sys
from pathlib import Path

# Add parent directory to path to import mcp_server
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import tools from mcp_server
# Note: We import the functions directly, not through MCP
from mcp_server import hello, calculate, get_server_info


class TestHelloTool:
    """Tests for the hello tool."""

    def test_hello_returns_greeting(self):
        """Test that hello returns a proper greeting."""
        result = hello("Alice")
        assert "Hello, Alice" in result
        assert "Welcome" in result

    def test_hello_with_different_names(self):
        """Test hello with various names."""
        names = ["Bob", "Charlie", "Dana"]
        for name in names:
            result = hello(name)
            assert name in result


class TestCalculateTool:
    """Tests for the calculate tool."""

    def test_addition(self):
        """Test addition operation."""
        result = calculate("add", 5, 3)
        data = json.loads(result)
        assert data["result"] == 8
        assert data["operation"] == "add"

    def test_subtraction(self):
        """Test subtraction operation."""
        result = calculate("subtract", 10, 4)
        data = json.loads(result)
        assert data["result"] == 6

    def test_multiplication(self):
        """Test multiplication operation."""
        result = calculate("multiply", 6, 7)
        data = json.loads(result)
        assert data["result"] == 42

    def test_division(self):
        """Test division operation."""
        result = calculate("divide", 15, 3)
        data = json.loads(result)
        assert data["result"] == 5

    def test_division_by_zero(self):
        """Test that division by zero returns error."""
        result = calculate("divide", 10, 0)
        data = json.loads(result)
        assert "error" in data
        assert "divide by zero" in data["error"].lower()

    def test_invalid_operation(self):
        """Test that invalid operation returns error."""
        result = calculate("modulo", 10, 3)
        data = json.loads(result)
        assert "error" in data
        assert "Unknown operation" in data["error"]


class TestServerInfo:
    """Tests for server info tool."""

    def test_server_info_structure(self):
        """Test that server info returns proper structure."""
        result = get_server_info()
        data = json.loads(result)

        # Check required fields exist
        assert "name" in data
        assert "version" in data
        assert "status" in data
        assert "capabilities" in data

    def test_server_capabilities(self):
        """Test that capabilities are listed."""
        result = get_server_info()
        data = json.loads(result)

        capabilities = data["capabilities"]
        assert "tools" in capabilities
        assert len(capabilities["tools"]) > 0

    def test_server_status(self):
        """Test that server reports running status."""
        result = get_server_info()
        data = json.loads(result)
        assert data["status"] == "running"


# Note: Async tests require pytest-asyncio
# Install with: pip install pytest-asyncio
#
# Example async test:
#
# import pytest
# from mcp_server import fetch_data
#
# class TestFetchData:
#     @pytest.mark.asyncio
#     async def test_fetch_data(self):
#         """Test async fetch_data tool."""
#         # This requires httpx to be installed
#         result = await fetch_data("https://httpbin.org/json")
#         data = json.loads(result)
#         assert data["status"] == 200
