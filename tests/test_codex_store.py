"""
Unit tests for Context Codex KnowledgeStore.
"""

import tempfile
import uuid
from pathlib import Path

import pytest

from context_foundry.codex import (
    BuildMetric,
    Evidence,
    KnowledgeEntry,
    KnowledgeStore,
    KnowledgeType,
    Severity,
    Solution,
    generate_entry_id,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    store = KnowledgeStore(db_path)
    yield store

    store.close()
    db_path.unlink()


class TestKnowledgeStore:
    """Test KnowledgeStore CRUD operations."""

    def test_add_and_get_entry(self, temp_db):
        """Test adding and retrieving a knowledge entry."""
        entry = KnowledgeEntry(
            id=generate_entry_id("issue"),
            type=KnowledgeType.ISSUE,
            category="common-issue",
            title="Docker volume config issue",
            description="Volumes persist old config",
            severity=Severity.MEDIUM,
            tags=["docker", "volumes"],
            project_types=["python", "nodejs"],
        )

        entry_id = temp_db.add_entry(entry)
        assert entry_id == entry.id

        retrieved = temp_db.get_entry(entry_id)
        assert retrieved is not None
        assert retrieved.title == "Docker volume config issue"
        assert retrieved.severity == Severity.MEDIUM
        assert "docker" in retrieved.tags
        assert "python" in retrieved.project_types

    def test_update_entry(self, temp_db):
        """Test updating a knowledge entry."""
        entry = KnowledgeEntry(
            id=generate_entry_id("issue"),
            type=KnowledgeType.ISSUE,
            category="common-issue",
            title="Original title",
            frequency=1,
        )

        temp_db.add_entry(entry)

        # Update the entry
        success = temp_db.update_entry(
            entry.id, {"title": "Updated title", "frequency": 5}
        )
        assert success is True

        retrieved = temp_db.get_entry(entry.id)
        assert retrieved.title == "Updated title"
        assert retrieved.frequency == 5

    def test_delete_entry(self, temp_db):
        """Test deleting a knowledge entry."""
        entry = KnowledgeEntry(
            id=generate_entry_id("issue"),
            type=KnowledgeType.ISSUE,
            category="common-issue",
            title="To be deleted",
        )

        temp_db.add_entry(entry)

        # Delete the entry
        success = temp_db.delete_entry(entry.id)
        assert success is True

        # Verify it's gone
        retrieved = temp_db.get_entry(entry.id)
        assert retrieved is None

    def test_increment_frequency(self, temp_db):
        """Test incrementing frequency counter."""
        entry = KnowledgeEntry(
            id=generate_entry_id("issue"),
            type=KnowledgeType.ISSUE,
            category="common-issue",
            title="Frequent issue",
            frequency=1,
        )

        temp_db.add_entry(entry)

        # Increment multiple times
        temp_db.increment_frequency(entry.id)
        temp_db.increment_frequency(entry.id)
        temp_db.increment_frequency(entry.id)

        retrieved = temp_db.get_entry(entry.id)
        assert retrieved.frequency == 4  # 1 + 3 increments


class TestSearch:
    """Test search operations."""

    def test_search_by_type(self, temp_db):
        """Test searching by type and category."""
        # Add multiple entries
        issue = KnowledgeEntry(
            id=generate_entry_id("issue"),
            type=KnowledgeType.ISSUE,
            category="common-issue",
            title="Issue 1",
        )

        pattern = KnowledgeEntry(
            id=generate_entry_id("pattern"),
            type=KnowledgeType.PATTERN,
            category="test-pattern",
            title="Pattern 1",
        )

        temp_db.add_entry(issue)
        temp_db.add_entry(pattern)

        # Search for issues
        results = temp_db.search_by_type("issue")
        assert len(results) == 1
        assert results[0].title == "Issue 1"

        # Search for patterns with category
        results = temp_db.search_by_type("pattern", category="test-pattern")
        assert len(results) == 1
        assert results[0].title == "Pattern 1"

    def test_search_by_tags(self, temp_db):
        """Test searching by tags."""
        entry1 = KnowledgeEntry(
            id=generate_entry_id("issue"),
            type=KnowledgeType.ISSUE,
            category="common-issue",
            title="Docker issue",
            tags=["docker", "volumes"],
        )

        entry2 = KnowledgeEntry(
            id=generate_entry_id("issue"),
            type=KnowledgeType.ISSUE,
            category="common-issue",
            title="Python issue",
            tags=["python", "flask"],
        )

        temp_db.add_entry(entry1)
        temp_db.add_entry(entry2)

        # Search for docker tag (should find entry1)
        results = temp_db.search_by_tags(["docker"])
        assert len(results) == 1
        assert results[0].title == "Docker issue"

        # Search for any of multiple tags (should find both)
        results = temp_db.search_by_tags(["docker", "python"], match_all=False)
        assert len(results) == 2

    def test_full_text_search(self, temp_db):
        """Test FTS5 full-text search."""
        entry = KnowledgeEntry(
            id=generate_entry_id("issue"),
            type=KnowledgeType.ISSUE,
            category="common-issue",
            title="Docker volume configuration",
            description="Volumes persist old database config",
            tags=["docker"],
        )

        temp_db.add_entry(entry)

        # Search for text in title
        results = temp_db.search("docker volume")
        assert len(results) == 1

        # Search for text in description
        results = temp_db.search("database config")
        assert len(results) == 1


class TestSolutions:
    """Test solution management."""

    def test_add_and_get_solutions(self, temp_db):
        """Test adding and retrieving solutions."""
        # Create an entry first
        entry = KnowledgeEntry(
            id=generate_entry_id("issue"),
            type=KnowledgeType.ISSUE,
            category="common-issue",
            title="Issue with solutions",
        )

        temp_db.add_entry(entry)

        # Add solutions
        solution1 = Solution(
            id="sol-001",
            entry_id=entry.id,
            phase="builder",
            description="Fix in builder phase",
            auto_apply=True,
            success_rate=0.95,
        )

        solution2 = Solution(
            id="sol-002",
            entry_id=entry.id,
            phase="scout",
            description="Check in scout phase",
            auto_apply=False,
        )

        temp_db.add_solution(solution1)
        temp_db.add_solution(solution2)

        # Get all solutions
        solutions = temp_db.get_solutions(entry.id)
        assert len(solutions) == 2

        # Get only auto-applicable solutions
        auto_solutions = temp_db.get_solutions(entry.id, auto_apply_only=True)
        assert len(auto_solutions) == 1
        assert auto_solutions[0].description == "Fix in builder phase"


class TestEvidence:
    """Test evidence management."""

    def test_add_and_get_evidence(self, temp_db):
        """Test adding and retrieving evidence."""
        # Create an entry first
        entry = KnowledgeEntry(
            id=generate_entry_id("issue"),
            type=KnowledgeType.ISSUE,
            category="common-issue",
            title="Issue with evidence",
        )

        temp_db.add_entry(entry)

        # Add evidence
        evidence = Evidence(
            id=str(uuid.uuid4()),
            entry_id=entry.id,
            evidence_type="symptom",
            description="Error message appears in logs",
            code_snippet="Error: database 'old_db' does not exist",
        )

        temp_db.add_evidence(evidence)

        # Retrieve evidence
        evidence_list = temp_db.get_evidence(entry.id)
        assert len(evidence_list) == 1
        assert evidence_list[0].description == "Error message appears in logs"


class TestRelationships:
    """Test knowledge relationships."""

    def test_add_and_get_relationships(self, temp_db):
        """Test adding and retrieving relationships between entries."""
        # Create two entries
        pattern = KnowledgeEntry(
            id=generate_entry_id("pattern"),
            type=KnowledgeType.PATTERN,
            category="architecture",
            title="Use named volumes",
        )

        issue = KnowledgeEntry(
            id=generate_entry_id("issue"),
            type=KnowledgeType.ISSUE,
            category="common-issue",
            title="Volume config persists",
        )

        temp_db.add_entry(pattern)
        temp_db.add_entry(issue)

        # Add relationship
        rel_id = temp_db.add_relationship(
            pattern.id,
            issue.id,
            "prevents",
            strength=0.9,
            description="Using named volumes prevents this issue",
        )

        assert rel_id != ""

        # Get related entries
        related = temp_db.get_related(pattern.id, "prevents")
        assert len(related) == 1
        assert related[0].title == "Volume config persists"


class TestProjectTracking:
    """Test project tracking functionality."""

    def test_track_project(self, temp_db):
        """Test tracking which projects encountered which knowledge."""
        # Create an entry
        entry = KnowledgeEntry(
            id=generate_entry_id("issue"),
            type=KnowledgeType.ISSUE,
            category="common-issue",
            title="Docker issue",
        )

        temp_db.add_entry(entry)

        # Track project first time
        project_id = temp_db.track_project(entry.id, "/path/to/project1", "python")
        assert project_id != ""

        # Track same project again (should increment occurrence)
        project_id2 = temp_db.track_project(entry.id, "/path/to/project1", "python")
        assert project_id2 == project_id  # Same record

        # Get projects for this entry
        projects = temp_db.get_projects_for_entry(entry.id)
        assert len(projects) == 1
        assert projects[0].project_path == "/path/to/project1"
        assert projects[0].occurrence_count >= 2  # Tracked twice

    def test_get_project_history(self, temp_db):
        """Test retrieving all knowledge encountered by a project."""
        # Create multiple entries
        issue1 = KnowledgeEntry(
            id=generate_entry_id("issue"),
            type=KnowledgeType.ISSUE,
            category="common-issue",
            title="Issue 1",
        )

        issue2 = KnowledgeEntry(
            id=generate_entry_id("issue"),
            type=KnowledgeType.ISSUE,
            category="common-issue",
            title="Issue 2",
        )

        temp_db.add_entry(issue1)
        temp_db.add_entry(issue2)

        # Track both for same project
        temp_db.track_project(issue1.id, "/path/to/project1")
        temp_db.track_project(issue2.id, "/path/to/project1")

        # Get project history
        history = temp_db.get_project_history("/path/to/project1")
        assert len(history) == 2
        assert any(e.title == "Issue 1" for e in history)
        assert any(e.title == "Issue 2" for e in history)


class TestBuildMetrics:
    """Test build metrics tracking."""

    def test_track_build(self, temp_db):
        """Test tracking build metrics."""
        metric = BuildMetric(
            id=str(uuid.uuid4()),
            job_id="job-123",
            project_path="/path/to/project",
            project_type="python",
            duration_seconds=120.5,
            phase_durations={"scout": 30.0, "builder": 90.5},
            success=True,
            exit_code=0,
            patterns_applied=["pat-001", "pat-002"],
            issues_encountered=["iss-001"],
        )

        metric_id = temp_db.track_build(metric)
        assert metric_id == metric.id

        # Retrieve metrics
        metrics = temp_db.get_metrics(project_path="/path/to/project")
        assert len(metrics) == 1
        assert metrics[0].duration_seconds == 120.5
        assert "pat-001" in metrics[0].patterns_applied

    def test_get_build_stats(self, temp_db):
        """Test build statistics."""
        # Add multiple builds
        metric1 = BuildMetric(
            id=str(uuid.uuid4()),
            project_path="/path/to/project",
            duration_seconds=100.0,
            success=True,
        )

        metric2 = BuildMetric(
            id=str(uuid.uuid4()),
            project_path="/path/to/project",
            duration_seconds=150.0,
            success=True,
        )

        metric3 = BuildMetric(
            id=str(uuid.uuid4()),
            project_path="/path/to/project",
            duration_seconds=200.0,
            success=False,
        )

        temp_db.track_build(metric1)
        temp_db.track_build(metric2)
        temp_db.track_build(metric3)

        # Get stats
        stats = temp_db.get_build_stats("/path/to/project")
        assert stats["total_builds"] == 3
        assert stats["successful_builds"] == 2
        assert stats["success_rate"] == pytest.approx(2 / 3)
        assert stats["avg_duration_seconds"] == pytest.approx(150.0)


class TestStatistics:
    """Test statistics queries."""

    def test_get_stats(self, temp_db):
        """Test getting Context Codex statistics."""
        # Add various entries
        for i in range(5):
            entry = KnowledgeEntry(
                id=generate_entry_id("issue"),
                type=KnowledgeType.ISSUE,
                category="common-issue",
                title=f"Issue {i}",
                frequency=i + 1,
            )
            temp_db.add_entry(entry)

        for i in range(3):
            entry = KnowledgeEntry(
                id=generate_entry_id("pattern"),
                type=KnowledgeType.PATTERN,
                category="test-pattern",
                title=f"Pattern {i}",
            )
            temp_db.add_entry(entry)

        stats = temp_db.get_stats()
        assert stats["total_entries"] == 8
        assert stats["entries_by_type"]["issue"] == 5
        assert stats["entries_by_type"]["pattern"] == 3
        assert len(stats["top_issues"]) == 5


def test_generate_entry_id():
    """Test entry ID generation."""
    issue_id = generate_entry_id("issue")
    assert issue_id.startswith("iss-")

    pattern_id = generate_entry_id("pattern")
    assert pattern_id.startswith("pat-")

    learning_id = generate_entry_id("learning")
    assert learning_id.startswith("lrn-")

    # Unknown type should use "ent" prefix
    unknown_id = generate_entry_id("unknown")
    assert unknown_id.startswith("ent-")
