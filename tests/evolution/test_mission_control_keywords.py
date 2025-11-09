"""Tests for Mission Control keyword handling logic"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tools.evolution.mission_control import MissionControlApp


class TestKeywordHandling:
    """Test suite for Mission Control keyword detection and handling"""

    @pytest.fixture
    def app(self):
        """Create a mock MissionControlApp instance"""
        app = MissionControlApp()
        # Mock the query_one method to avoid Textual dependencies
        app.query_one = MagicMock()
        return app

    @pytest.mark.asyncio
    async def test_greeting_keywords(self, app):
        """Test that greetings don't trigger builds"""
        greetings = ["hi", "hello", "hey", "greetings", "good morning"]

        for greeting in greetings:
            result = await app._process_command(greeting)
            assert "Hello" in result or "What would you like" in result
            # Should NOT start a build
            assert "Starting build" not in result

    @pytest.mark.asyncio
    async def test_short_messages_dont_trigger_builds(self, app):
        """Test that short messages (≤2 words) don't accidentally trigger builds"""
        short_messages = ["ok", "yes please", "no", "sure", "great"]

        for msg in short_messages:
            result = await app._process_command(msg)
            # Should either greet or ask for clarification, but NOT start a build
            assert "Starting build" not in result

    @pytest.mark.asyncio
    async def test_query_keywords_show_shortcuts(self, app):
        """Test that query keywords show shortcut tips"""
        # Note: "get status" will trigger status command because "status" is a keyword
        # So we test with queries that don't have other keywords
        queries = ["get details", "show info", "list items", "view results"]

        for query in queries:
            result = await app._process_command(query)
            assert "Tab to switch views" in result or "help" in result.lower()
            # Should NOT start a build
            assert "Starting build" not in result

    @pytest.mark.asyncio
    async def test_status_keyword(self, app):
        """Test status keyword invokes MCP status"""
        with patch.object(app, '_get_mcp_status', new=AsyncMock(return_value="MCP Status Info")):
            result = await app._process_command("status")
            assert "MCP Status Info" in result or "Status" in result

    @pytest.mark.asyncio
    async def test_build_keywords_trigger_builds(self, app):
        """Test that build keywords trigger autonomous builds"""
        build_keywords = [
            "build a calculator app",
            "create a todo list",
            "make a weather app",
            "develop a chat bot",
            "implement user auth",
            "write a script",
            "design a dashboard",
            "upgrade my project",
            "fix the bug",
            "update the UI",
            "add dark mode",
            "modify the layout"
        ]

        with patch.object(app, '_start_autonomous_build', new=AsyncMock(return_value="Build started!")):
            for keyword_phrase in build_keywords:
                result = await app._process_command(keyword_phrase)
                assert result == "Build started!"

    @pytest.mark.asyncio
    async def test_help_keyword(self, app):
        """Test help keyword shows available commands"""
        help_queries = ["help", "what can you do", "how do I use this"]

        for query in help_queries:
            result = await app._process_command(query)
            assert "Commands" in result or "Keyboard" in result
            assert "help" in result.lower() or "Tab" in result

    @pytest.mark.asyncio
    async def test_unclear_intent_asks_for_clarification(self, app):
        """Test that unclear messages ask for clarification"""
        unclear = ["something", "random text", "xyz abc"]

        for msg in unclear:
            result = await app._process_command(msg)
            assert "not sure" in result.lower() or "help" in result.lower()
            # Should NOT start a build
            assert "Starting build" not in result

    @pytest.mark.asyncio
    async def test_case_insensitive_keywords(self, app):
        """Test that keyword detection is case-insensitive"""
        with patch.object(app, '_start_autonomous_build', new=AsyncMock(return_value="Build started!")):
            variants = ["BUILD a calculator", "Create a TODO", "MAKE a game"]
            for variant in variants:
                result = await app._process_command(variant)
                assert result == "Build started!"

    @pytest.mark.asyncio
    async def test_greeting_variants_not_triggering_builds(self, app):
        """Test various greeting styles don't start builds"""
        # Test exact greetings that should return welcome message
        exact_greetings = ["hi", "hello", "hey", "yo", "sup", "good morning", "good afternoon", "good evening"]

        for greeting in exact_greetings:
            result = await app._process_command(greeting)
            # Should return a welcome message, not a build
            assert "Welcome" in result or "Hello" in result
            assert "Build started successfully" not in result

        # Test multi-word greetings that may get clarification response
        multi_word_greetings = ["hello there", "hey!", "hi everyone"]
        for greeting in multi_word_greetings:
            result = await app._process_command(greeting)
            # Should NOT start a build, regardless of response type
            assert "Starting build" not in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
