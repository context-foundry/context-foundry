"""
Tests for ConversationParser - Natural language parsing
"""

from tools.tui_daemon.conversation_parser import ConversationParser


class TestConversationParser:
    """Test suite for ConversationParser"""

    def test_simple_build(self):
        """Test parsing simple build request"""
        parser = ConversationParser()
        result = parser.parse("build a todo app with react")

        assert "todo app" in result.task.lower()
        assert "react" in result.task.lower()
        assert result.mode == "smart"
        assert result.max_iterations == 5
        assert result.timeout == 3600

    def test_extract_directory(self):
        """Test directory extraction"""
        parser = ConversationParser()
        result = parser.parse("create a fastapi backend in ~/api")

        assert result.working_directory == "~/api"
        assert "fastapi" in result.task.lower()

    def test_extract_timeout(self):
        """Test timeout extraction"""
        parser = ConversationParser()

        # Test minutes
        result = parser.parse("build app timeout 30m")
        assert result.timeout == 1800

        # Test hours
        result = parser.parse("build app timeout 2h")
        assert result.timeout == 7200

        # Test seconds
        result = parser.parse("build app timeout 120s")
        assert result.timeout == 120

    def test_extract_iterations(self):
        """Test iterations extraction"""
        parser = ConversationParser()
        result = parser.parse("build python cli iterations 3")

        assert result.max_iterations == 3

    def test_extract_github_repo(self):
        """Test GitHub repo extraction"""
        parser = ConversationParser()

        # Test full URL
        result = parser.parse("create app from github.com/user/project")
        assert result.github_repo == "user/project"

        # Test short form
        result = parser.parse("create app repo: user/project")
        assert result.github_repo == "user/project"

    def test_extract_mode(self):
        """Test mode extraction"""
        parser = ConversationParser()

        result = parser.parse("build app quick mode")
        assert result.mode == "quick"

        result = parser.parse("build app thorough mode")
        assert result.mode == "thorough"

        result = parser.parse("build app custom mode")
        assert result.mode == "custom"

    def test_infer_directory(self):
        """Test directory inference"""
        parser = ConversationParser()

        result = parser.parse("build a todo app")
        assert "todo" in result.working_directory.lower()
        assert "homelab" in result.working_directory

        result = parser.parse("create a react project")
        assert "react" in result.working_directory.lower()

    def test_confidence_calculation(self):
        """Test confidence scoring"""
        parser = ConversationParser()

        # High confidence: has action, project type, directory
        result = parser.parse("build a react app in ~/projects/myapp")
        assert result.confidence >= 0.6

        # Low confidence: vague input
        result = parser.parse("make something")
        assert result.confidence < 0.4

    def test_complex_parse(self):
        """Test parsing complex input with multiple parameters"""
        parser = ConversationParser()
        result = parser.parse(
            "build a todo app with react in ~/projects/todo "
            "timeout 1h iterations 5 quick mode repo: user/todo-app"
        )

        assert "todo app" in result.task.lower()
        assert result.working_directory == "~/projects/todo"
        assert result.timeout == 3600
        assert result.max_iterations == 5
        assert result.mode == "quick"
        assert result.github_repo == "user/todo-app"

    def test_task_cleaning(self):
        """Test that extracted task is clean of metadata"""
        parser = ConversationParser()
        result = parser.parse(
            "build a game in ~/projects/snake timeout 30m iterations 3"
        )

        # Task should not contain directory, timeout, or iterations
        assert "~/projects" not in result.task
        assert "timeout" not in result.task.lower()
        assert "iterations" not in result.task.lower()
        assert "game" in result.task.lower()
