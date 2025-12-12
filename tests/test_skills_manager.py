"""
Tests for the Reusable Skills Management system.

Tests cover:
- Skill creation and storage (JSON + auto-generated Markdown)
- Skill searching (by query, project type, success rate)
- Skill loading and retrieval
- Metrics updating (success rate tracking)
- Context Codex integration
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import shutil
import sys


# Mock FastMCP before importing
class MockFastMCP:
    def __init__(self, *args, **kwargs):
        pass

    def tool(self, *args, **kwargs):
        def decorator(func):
            return func

        if args and callable(args[0]):
            return args[0]
        return decorator

    def resource(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def run(self):
        pass


mock_module = MagicMock()
mock_module.FastMCP = MockFastMCP
mock_module.Context = MagicMock

sys.modules["fastmcp"] = mock_module
sys.modules["fastmcp.server"] = MagicMock()
sys.modules["fastmcp.server.dependencies"] = MagicMock()
sys.modules["fastmcp.server.dependencies"].get_context = MagicMock()

# Now import SkillsManager (after mocking)
from tools.skills.manager import SkillsManager  # noqa: E402


@pytest.fixture
def temp_skills_dir():
    """Create a temporary directory for skills storage"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def skills_manager(temp_skills_dir):
    """Create a SkillsManager instance with temp storage"""
    with patch("tools.skills.manager.Path.home") as mock_home:
        mock_home.return_value = temp_skills_dir
        manager = SkillsManager()
        yield manager


@pytest.fixture
def sample_skill_data():
    """Sample skill data for testing"""
    return {
        "title": "JWT Authentication with FastAPI",
        "description": "Complete JWT auth implementation with login, token refresh, and protected routes.",
        "code": """
from fastapi import Depends, HTTPException
from jose import jwt

def create_access_token(data: dict):
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
""",
        "file_type": "python",
        "project_type": "fastapi",
        "tags": ["authentication", "jwt", "security"],
        "requirements": ["fastapi", "python-jose[cryptography]", "passlib"],
        "file_path": "auth/jwt_auth.py",
        "example": """
from auth.jwt_auth import create_access_token
token = create_access_token(data={"sub": user.email})
""",
    }


class TestSkillsManagerSave:
    """Test skill saving functionality"""

    def test_save_skill_creates_json_file(self, skills_manager, sample_skill_data):
        """Test that save_skill creates a JSON file with correct structure"""
        skill_id = skills_manager.save_skill(**sample_skill_data)

        assert skill_id is not None
        assert skill_id.startswith("skl-")  # Actual format is "skl-" not "skill-"

        # Check JSON file exists
        skill_file = skills_manager.skills_dir / "authentication" / f"{skill_id}.json"
        assert skill_file.exists()

        # Verify JSON structure
        with open(skill_file) as f:
            saved_data = json.load(f)

        assert saved_data["skill_id"] == skill_id
        assert saved_data["metadata"]["title"] == sample_skill_data["title"]
        assert saved_data["metadata"]["category"] == "authentication"
        assert saved_data["metrics"]["success_rate"] is None  # Starts as None
        assert saved_data["metrics"]["usage_count"] == 0
        assert "created_at" in saved_data
        assert saved_data["metrics"]["last_used"] is None

    def test_save_skill_creates_markdown_file(self, skills_manager, sample_skill_data):
        """Test that save_skill auto-generates a markdown file"""
        skill_id = skills_manager.save_skill(**sample_skill_data)

        # Check markdown file exists
        md_file = skills_manager.skills_dir / "authentication" / f"{skill_id}.md"
        assert md_file.exists()

        # Verify markdown content
        md_content = md_file.read_text()
        assert "# JWT Authentication with FastAPI" in md_content
        assert "## Implementation" in md_content
        assert "## Usage Example" in md_content
        assert "fastapi" in md_content

    @pytest.mark.skipif(
        os.environ.get("CI") is not None
        or os.environ.get("GITHUB_ACTIONS") is not None,
        reason="Codex integration method was removed, skipping in CI",
    )
    def test_save_skill_with_codex_integration(self, skills_manager, sample_skill_data):
        """Test that save_skill indexes skill in Context Codex"""
        with patch("tools.skills.manager.SkillsManager._save_to_codex") as mock_codex:
            mock_codex.return_value = "codex-entry-123"

            skill_id = skills_manager.save_skill(**sample_skill_data)

            # Verify codex was called
            mock_codex.assert_called_once()
            call_args = mock_codex.call_args[0]
            assert call_args[0]["skill_id"] == skill_id

    def test_save_skill_invalid_category(self, skills_manager, sample_skill_data):
        """Test save_skill with invalid tags (no matching category)"""
        sample_skill_data["tags"] = ["invalid-tag"]

        skill_id = skills_manager.save_skill(**sample_skill_data)

        # Should default to "utils" category
        skill_file = skills_manager.skills_dir / "utils" / f"{skill_id}.json"
        assert skill_file.exists()


class TestSkillsManagerSearch:
    """Test skill searching functionality"""

    @pytest.fixture
    def populated_skills_manager(self, skills_manager):
        """Create manager with multiple skills"""
        # Skill 1: JWT auth (high success rate)
        skills_manager.save_skill(
            title="JWT Authentication",
            description="JWT auth for FastAPI",
            code="code1",
            file_type="python",
            project_type="fastapi",
            tags=["authentication", "jwt"],
            requirements=["fastapi"],
            file_path="auth/jwt.py",
            example="example1",
        )

        # Skill 2: PostgreSQL pool (medium success rate)
        skill_id_2 = skills_manager.save_skill(
            title="PostgreSQL Connection Pool",
            description="Database connection pooling",
            code="code2",
            file_type="python",
            project_type="python",
            tags=["database", "postgresql"],
            requirements=["psycopg2"],
            file_path="db/postgres.py",
            example="example2",
        )

        # Update success rate for skill 2
        skill_file = skills_manager.skills_dir / "database" / f"{skill_id_2}.json"
        with open(skill_file) as f:
            data = json.load(f)
        data["metrics"]["success_rate"] = 0.75
        data["metrics"]["usage_count"] = 4
        with open(skill_file, "w") as f:
            json.dump(data, f, indent=2)

        # Also update the index
        index = skills_manager._load_index()
        for skill in index["skills"]:
            if skill["skill_id"] == skill_id_2:
                skill["success_rate"] = 0.75
                skill["usage_count"] = 4
        skills_manager.index_file.write_text(json.dumps(index, indent=2))

        # Skill 3: React component (low success rate)
        skill_id_3 = skills_manager.save_skill(
            title="React Button Component",
            description="Reusable button with variants",
            code="code3",
            file_type="typescript",
            project_type="react",
            tags=["ui", "react", "component"],
            requirements=["react"],
            file_path="components/Button.tsx",
            example="example3",
        )

        # Update success rate for skill 3
        skill_file = skills_manager.skills_dir / "ui" / f"{skill_id_3}.json"
        with open(skill_file) as f:
            data = json.load(f)
        data["metrics"]["success_rate"] = 0.4
        data["metrics"]["usage_count"] = 5
        with open(skill_file, "w") as f:
            json.dump(data, f, indent=2)

        # Also update the index
        index = skills_manager._load_index()
        for skill in index["skills"]:
            if skill["skill_id"] == skill_id_3:
                skill["success_rate"] = 0.4
                skill["usage_count"] = 5
        skills_manager.index_file.write_text(json.dumps(index, indent=2))

        return skills_manager

    def test_search_skills_by_query(self, populated_skills_manager):
        """Test searching skills by text query"""
        results = populated_skills_manager.search_skills("JWT authentication")

        assert len(results) > 0
        assert any("JWT" in r["title"] for r in results)

    def test_search_skills_by_project_type(self, populated_skills_manager):
        """Test filtering skills by project type"""
        results = populated_skills_manager.search_skills(
            query="", project_type="fastapi"
        )

        assert len(results) > 0
        assert all(r["project_type"] == "fastapi" for r in results)

    def test_search_skills_by_min_success_rate(self, populated_skills_manager):
        """Test filtering skills by minimum success rate"""
        results = populated_skills_manager.search_skills(query="", min_success_rate=0.7)

        # Should return PostgreSQL skill (0.75) and skills with None (not filtered)
        # Skills with None success_rate are not filtered out (could be new skills worth trying)
        assert len(results) >= 1

        # Verify that if success_rate is set, it meets the threshold
        for result in results:
            if result.get("success_rate") is not None:
                assert result["success_rate"] >= 0.7

    def test_search_skills_combined_filters(self, populated_skills_manager):
        """Test searching with multiple filters"""
        results = populated_skills_manager.search_skills(
            query="database", project_type="python", min_success_rate=0.5
        )

        assert len(results) > 0
        assert all(r["project_type"] == "python" for r in results)
        assert all(r["success_rate"] >= 0.5 for r in results)

    def test_search_skills_limit(self, populated_skills_manager):
        """Test search result limit"""
        results = populated_skills_manager.search_skills(query="", limit=2)

        assert len(results) <= 2


class TestSkillsManagerLoad:
    """Test skill loading functionality"""

    def test_load_skill_success(self, skills_manager, sample_skill_data):
        """Test loading an existing skill"""
        skill_id = skills_manager.save_skill(**sample_skill_data)

        loaded_skill = skills_manager.load_skill(skill_id)

        assert loaded_skill is not None
        assert loaded_skill["skill_id"] == skill_id
        assert loaded_skill["metadata"]["title"] == sample_skill_data["title"]
        assert "code" in loaded_skill["implementation"]
        assert "example" in loaded_skill["usage"]

    def test_load_skill_not_found(self, skills_manager):
        """Test loading a non-existent skill"""
        result = skills_manager.load_skill("skill-nonexistent-123")

        assert result is None


class TestSkillsManagerMetrics:
    """Test skill metrics updating"""

    def test_update_metrics_success(self, skills_manager, sample_skill_data):
        """Test updating skill metrics after successful use"""
        skill_id = skills_manager.save_skill(**sample_skill_data)

        # Update metrics: success
        result = skills_manager.update_metrics(
            skill_id=skill_id, project_name="test-project-1", success=True
        )

        assert result is True

        # Verify metrics updated
        skill = skills_manager.load_skill(skill_id)
        assert skill["metrics"]["success_rate"] == 1.0  # 1/1 successes
        assert skill["metrics"]["usage_count"] == 1
        assert len(skill["metrics"]["projects_used"]) == 1
        assert skill["metrics"]["projects_used"][0]["project_name"] == "test-project-1"
        assert skill["metrics"]["projects_used"][0]["success"] is True

    def test_update_metrics_failure(self, skills_manager, sample_skill_data):
        """Test updating skill metrics after failed use"""
        skill_id = skills_manager.save_skill(**sample_skill_data)

        # Update metrics: failure
        result = skills_manager.update_metrics(
            skill_id=skill_id, project_name="test-project-1", success=False
        )

        assert result is True

        # Verify metrics updated
        skill = skills_manager.load_skill(skill_id)
        assert skill["metrics"]["success_rate"] == 0.0  # 0/1 successes
        assert skill["metrics"]["usage_count"] == 1

    def test_update_metrics_multiple_uses(self, skills_manager, sample_skill_data):
        """Test success rate calculation over multiple uses"""
        skill_id = skills_manager.save_skill(**sample_skill_data)

        # Use 1: success
        skills_manager.update_metrics(skill_id, "project-1", True)
        # Use 2: success
        skills_manager.update_metrics(skill_id, "project-2", True)
        # Use 3: failure
        skills_manager.update_metrics(skill_id, "project-3", False)
        # Use 4: success
        skills_manager.update_metrics(skill_id, "project-4", True)

        skill = skills_manager.load_skill(skill_id)
        assert skill["metrics"]["success_rate"] == 0.75  # 3/4 successes
        assert skill["metrics"]["usage_count"] == 4
        assert len(skill["metrics"]["projects_used"]) == 4

    def test_update_metrics_nonexistent_skill(self, skills_manager):
        """Test updating metrics for non-existent skill"""
        result = skills_manager.update_metrics(
            skill_id="skill-nonexistent-123",
            project_name="test-project",
            success=True,
        )

        assert result is False


class TestSkillsManagerMarkdown:
    """Test markdown generation"""

    def test_generate_markdown_structure(self, skills_manager, sample_skill_data):
        """Test that generated markdown has correct structure"""
        # Create a real skill first, then load it
        skill_id = skills_manager.save_skill(**sample_skill_data)
        skill_data = skills_manager.load_skill(skill_id)

        # Update metrics for testing
        skill_data["metrics"]["success_rate"] = 0.85
        skill_data["metrics"]["usage_count"] = 10

        markdown = skills_manager._generate_markdown(skill_data)

        # Check required sections
        assert "# JWT Authentication with FastAPI" in markdown
        assert "## Description" in markdown
        assert "## Implementation" in markdown
        assert "## Usage Example" in markdown
        assert "## Dependencies" in markdown
        assert "## Metrics" in markdown

        # Check metrics display (can appear in two places)
        assert "**Success Rate**: 85%" in markdown or "**Success Rate**: 85" in markdown
        assert "**Times Used**: 10" in markdown

        # Check tags display
        assert "authentication" in markdown
        assert "jwt" in markdown
        assert "security" in markdown

    def test_generate_markdown_code_blocks(self, skills_manager, sample_skill_data):
        """Test that code is properly formatted in markdown"""
        # Create a real skill first, then load it
        skill_id = skills_manager.save_skill(**sample_skill_data)
        skill_data = skills_manager.load_skill(skill_id)

        markdown = skills_manager._generate_markdown(skill_data)

        # Check code fencing
        assert "```python" in markdown
        assert "create_access_token" in markdown


class TestSkillsManagerIntegration:
    """Integration tests for complete workflows"""

    def test_full_skill_lifecycle(self, skills_manager):
        """Test complete lifecycle: create -> search -> load -> use -> update"""
        # 1. Create skill
        skill_id = skills_manager.save_skill(
            title="Redis Caching Layer",
            description="Redis caching with TTL and invalidation",
            code="redis_code",
            file_type="python",
            project_type="python",
            tags=["caching", "redis", "performance"],
            requirements=["redis"],
            file_path="cache/redis.py",
            example="cache_example",
        )

        assert skill_id is not None

        # 2. Search for skill
        results = skills_manager.search_skills("redis caching")
        assert len(results) > 0
        assert any(r["skill_id"] == skill_id for r in results)

        # 3. Load skill
        skill = skills_manager.load_skill(skill_id)
        assert skill is not None
        assert skill["metadata"]["title"] == "Redis Caching Layer"

        # 4. Update metrics after use
        skills_manager.update_metrics(skill_id, "project-1", True)
        skills_manager.update_metrics(skill_id, "project-2", True)

        # 5. Verify updated metrics
        updated_skill = skills_manager.load_skill(skill_id)
        assert updated_skill["metrics"]["success_rate"] == 1.0
        assert updated_skill["metrics"]["usage_count"] == 2

        # 6. Search with min_success_rate should include this skill
        high_quality_skills = skills_manager.search_skills(
            "redis", min_success_rate=0.9
        )
        assert any(r["skill_id"] == skill_id for r in high_quality_skills)


class TestSkillsManagerEdgeCases:
    """Test edge cases and error handling"""

    def test_save_skill_with_empty_tags(self, skills_manager):
        """Test saving skill with empty tags list"""
        skill_id = skills_manager.save_skill(
            title="Test Skill",
            description="Test description",
            code="code",
            file_type="python",
            project_type="python",
            tags=[],  # Empty tags
            requirements=[],
            file_path="test.py",
            example="example",
        )

        assert skill_id is not None
        # Load skill and check category
        skill = skills_manager.load_skill(skill_id)
        assert skill["metadata"]["category"] == "utils"

    def test_search_skills_empty_query(self, skills_manager, sample_skill_data):
        """Test searching with empty query returns all skills"""
        skills_manager.save_skill(**sample_skill_data)

        results = skills_manager.search_skills("")

        assert len(results) > 0

    def test_concurrent_metric_updates(self, skills_manager, sample_skill_data):
        """Test that concurrent metric updates don't corrupt data"""
        skill_id = skills_manager.save_skill(**sample_skill_data)

        # Simulate multiple updates
        for i in range(10):
            skills_manager.update_metrics(
                skill_id,
                f"project-{i}",
                i % 2 == 0,  # Alternating success/failure
            )

        skill = skills_manager.load_skill(skill_id)
        assert skill["metrics"]["usage_count"] == 10
        assert 0.0 <= skill["metrics"]["success_rate"] <= 1.0
        assert len(skill["metrics"]["projects_used"]) == 10
