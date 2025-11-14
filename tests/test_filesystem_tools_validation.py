"""
Additional tests for filesystem tool validation and cache management

Tests the fixes for:
- Parameter validation enforcement
- Cache clearing on force_refresh
- Cache key collision prevention (category/name)
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.mcp_utils.filesystem_tools import (
    ToolDiscoveryScanner,
    ToolExecutor,
    ToolMetadata,
    ToolParameter,
)


class TestParameterValidation:
    """Test parameter validation enforcement"""

    def test_validate_required_parameters_enforced(self):
        """Test that missing required parameters raise ValueError"""
        executor = ToolExecutor()

        tool = ToolMetadata(
            name="test_tool",
            category="test",
            file_path=Path("/tmp/test.py"),
            description="Test",
            parameters=[
                ToolParameter(
                    name="required_param",
                    type="str",
                    required=True,
                    description="Required parameter",
                ),
                ToolParameter(
                    name="optional_param",
                    type="str",
                    required=False,
                    default="default",
                    description="Optional parameter",
                ),
            ],
        )

        # Should fail - missing required param
        with pytest.raises(ValueError, match="missing required parameters"):
            executor._validate_parameters(tool, {})

        # Should fail - missing required param (only optional provided)
        with pytest.raises(ValueError, match="missing required parameters"):
            executor._validate_parameters(tool, {"optional_param": "value"})

        # Should pass - required param provided
        executor._validate_parameters(tool, {"required_param": "value"})

        # Should pass - both provided
        executor._validate_parameters(
            tool, {"required_param": "value", "optional_param": "other"}
        )

    def test_real_tool_parameter_parsing(self):
        """Test that real tools have parameters parsed correctly"""
        scanner = ToolDiscoveryScanner()
        tools = scanner.discover_tools(force_refresh=True)

        if not tools:
            pytest.skip("No tools found in filesystem")

        # Find a tool with parameters
        tool_with_params = None
        for tool in tools:
            if len(tool.parameters) > 0:
                tool_with_params = tool
                break

        if not tool_with_params:
            pytest.skip("No tools with parameters found")

        # Verify parameters are populated
        assert len(tool_with_params.parameters) > 0

        # Verify each parameter has required fields
        for param in tool_with_params.parameters:
            assert param.name
            assert param.type
            assert isinstance(param.required, bool)

        # Verify signature includes parameter names
        signature = tool_with_params.get_signature()
        assert tool_with_params.name in signature
        assert tool_with_params.parameters[0].name in signature

    def test_parameter_validation_with_real_tool(self):
        """Test validation with a real tool from filesystem"""
        scanner = ToolDiscoveryScanner()
        scanner.discover_tools(force_refresh=True)

        tool = scanner.get_tool("search")
        if not tool:
            pytest.skip("search tool not found")

        executor = ToolExecutor()

        # Should fail - missing required 'query' parameter
        with pytest.raises(ValueError, match="missing required parameters"):
            executor._validate_parameters(tool, {})

        # Should pass - required parameter provided
        executor._validate_parameters(tool, {"query": "test"})


class TestCacheManagement:
    """Test cache management fixes"""

    def test_cache_cleared_on_force_refresh(self):
        """Test that cache is cleared when force_refresh=True"""
        scanner = ToolDiscoveryScanner()

        # First discovery
        scanner.discover_tools(force_refresh=True)
        cache_size_1 = len(scanner._tool_cache)

        # Manually add a fake entry to cache
        fake_tool = ToolMetadata(
            name="fake_deleted_tool",
            category="test",
            file_path=Path("/tmp/nonexistent.py"),
            description="This should be cleared",
        )
        fake_key = f"{fake_tool.category}/{fake_tool.name}"
        scanner._tool_cache[fake_key] = fake_tool

        # Verify fake entry is in cache
        assert len(scanner._tool_cache) == cache_size_1 + 1

        # Force refresh - should clear cache
        scanner.discover_tools(force_refresh=True)

        # Fake entry should be gone
        assert fake_key not in scanner._tool_cache
        assert len(scanner._tool_cache) == cache_size_1

    def test_cache_key_uses_category_and_name(self):
        """Test that cache keys use category/name format to prevent collisions"""
        scanner = ToolDiscoveryScanner()
        scanner.discover_tools(force_refresh=True)

        # Cache keys should be in format "category/name"
        for cache_key, tool in scanner._tool_cache.items():
            expected_key = f"{tool.category}/{tool.name}"
            assert cache_key == expected_key, (
                f"Cache key {cache_key} doesn't match expected {expected_key}"
            )

    def test_tools_in_different_categories_dont_collide(self):
        """Test that tools with same name in different categories don't overwrite"""
        scanner = ToolDiscoveryScanner()

        # Create two tools with same name, different categories
        tool1 = ToolMetadata(
            name="common_name",
            category="category1",
            file_path=Path("/tmp/cat1/common_name.py"),
            description="Tool 1",
        )

        tool2 = ToolMetadata(
            name="common_name",
            category="category2",
            file_path=Path("/tmp/cat2/common_name.py"),
            description="Tool 2",
        )

        # Manually add to cache
        scanner._tool_cache[f"{tool1.category}/{tool1.name}"] = tool1
        scanner._tool_cache[f"{tool2.category}/{tool2.name}"] = tool2

        # Both should exist in cache
        assert len(scanner._tool_cache) == 2

        # Get tool should find correct one when category specified
        found1 = scanner.get_tool("common_name", category="category1")
        found2 = scanner.get_tool("common_name", category="category2")

        assert found1 is not None
        assert found2 is not None
        assert found1.category == "category1"
        assert found2.category == "category2"

    def test_get_tool_searches_all_categories_when_category_not_specified(self):
        """Test that get_tool searches across all categories when category not given"""
        scanner = ToolDiscoveryScanner()
        scanner.discover_tools(force_refresh=True)

        # Get a tool without specifying category
        for tool in scanner._tool_cache.values():
            found = scanner.get_tool(tool.name)
            assert found is not None
            assert found.name == tool.name
            break


class TestCachePersistence:
    """Test cache saving and loading"""

    def test_cache_saves_with_correct_keys(self):
        """Test that cache saves with category/name keys"""
        scanner = ToolDiscoveryScanner()
        scanner.discover_tools(force_refresh=True)

        # Save cache
        scanner._save_cache()

        # Load cache data directly
        if scanner._cache_file.exists():
            cache_data = json.loads(scanner._cache_file.read_text())

            # All keys should have category/name format
            for cache_key in cache_data.keys():
                assert "/" in cache_key, (
                    f"Cache key {cache_key} missing category separator"
                )

    def test_cache_loads_with_correct_keys(self):
        """Test that cache loads and reconstructs with category/name keys"""
        scanner1 = ToolDiscoveryScanner()
        scanner1.discover_tools(force_refresh=True)

        # Save cache
        scanner1._save_cache()

        # Create new scanner and load from cache
        scanner2 = ToolDiscoveryScanner()
        loaded = scanner2._load_cache()

        if loaded:
            # All cache keys should have category/name format
            for cache_key, tool in scanner2._tool_cache.items():
                expected_key = f"{tool.category}/{tool.name}"
                assert cache_key == expected_key


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
