"""
Tests for the CLI tree command.

Tests cover:
- cfd tree <job_id> command
- JSON output format
- ASCII tree output format
- Error handling for non-existent jobs
"""

import json
import pytest
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

from context_foundry.daemon.cli import cmd_tree
from context_foundry.daemon.store import Store
from context_foundry.daemon.state_machine import StateMachine
from context_foundry.daemon.models import Job, JobType
from context_foundry.daemon.config import Config


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield db_path


@pytest.fixture
def store(temp_db):
    """Create a Store instance with a temporary database."""
    return Store(temp_db)


@pytest.fixture
def state_machine(store):
    """Create a StateMachine instance."""
    return StateMachine(store)


@pytest.fixture
def sample_job(store):
    """Create a sample job for testing."""
    job = Job.create(
        job_type=JobType.AUTONOMOUS_BUILD,
        params={"task": "Build a test app", "working_directory": "/tmp/test"},
        priority=5,
    )
    store.save_job(job)
    return job


@pytest.fixture
def mock_args(temp_db, sample_job):
    """Create mock arguments for cmd_tree."""
    args = MagicMock()
    args.config = None
    args.job_id = sample_job.id
    args.json = False
    return args


@pytest.fixture
def mock_config(temp_db):
    """Create a mock config that uses temp db."""
    config = MagicMock(spec=Config)
    config.db_path = temp_db
    return config


# =============================================================================
# CMD_TREE TESTS
# =============================================================================


class TestCmdTree:
    """Tests for cmd_tree function."""

    def test_tree_ascii_output(self, store, sample_job, mock_config):
        """cmd_tree outputs ASCII tree format by default."""
        args = MagicMock()
        args.config = None
        args.job_id = sample_job.id
        args.json = False

        with patch("context_foundry.daemon.cli.Config.load", return_value=mock_config):
            with patch("context_foundry.daemon.cli.Store", return_value=store):
                # Capture stdout
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    result = cmd_tree(args)
                    output = mock_stdout.getvalue()

        assert result == 0
        assert sample_job.id[:8] in output
        # Job with no tasks shows no phases (dynamic phase discovery)
        assert (
            "QUEUED" in output
            or "RUNNING" in output
            or sample_job.status.value.upper() in output
        )

    def test_tree_json_output(self, store, sample_job, mock_config):
        """cmd_tree outputs JSON when --json flag is set."""
        args = MagicMock()
        args.config = None
        args.job_id = sample_job.id
        args.json = True

        with patch("context_foundry.daemon.cli.Config.load", return_value=mock_config):
            with patch("context_foundry.daemon.cli.Store", return_value=store):
                # Capture stdout
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    result = cmd_tree(args)
                    output = mock_stdout.getvalue()

        assert result == 0

        # Parse JSON output
        data = json.loads(output)
        assert data["job_id"] == sample_job.id
        assert "phases" in data

    def test_tree_not_found(self, store, mock_config):
        """cmd_tree returns error for non-existent job."""
        args = MagicMock()
        args.config = None
        args.job_id = "nonexistent-job-id"
        args.json = False

        with patch("context_foundry.daemon.cli.Config.load", return_value=mock_config):
            with patch("context_foundry.daemon.cli.Store", return_value=store):
                # Capture stderr
                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    result = cmd_tree(args)
                    output = mock_stderr.getvalue()

        assert result == 1
        assert "Error:" in output

    def test_tree_shows_phases(self, store, sample_job, state_machine, mock_config):
        """cmd_tree shows phase structure."""
        # Start job and create tasks
        state_machine.start_job(sample_job.id)

        for i, phase in enumerate(["Scout", "Builder"]):
            task = state_machine.create_task_for_phase(sample_job.id, phase, i, 300)
            state_machine.start_task(task.id)
            if phase == "Scout":
                state_machine.complete_task(task.id, result={})

        args = MagicMock()
        args.config = None
        args.job_id = sample_job.id
        args.json = False

        with patch("context_foundry.daemon.cli.Config.load", return_value=mock_config):
            with patch("context_foundry.daemon.cli.Store", return_value=store):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    result = cmd_tree(args)
                    output = mock_stdout.getvalue()

        assert result == 0
        assert "Scout" in output
        assert "Builder" in output
        assert "SUCCEEDED" in output
        assert "RUNNING" in output

    def test_tree_json_structure(self, store, sample_job, state_machine, mock_config):
        """cmd_tree JSON output has correct structure."""
        state_machine.start_job(sample_job.id)
        task = state_machine.create_task_for_phase(sample_job.id, "Scout", 0, 300)
        state_machine.start_task(task.id)

        args = MagicMock()
        args.config = None
        args.job_id = sample_job.id
        args.json = True

        with patch("context_foundry.daemon.cli.Config.load", return_value=mock_config):
            with patch("context_foundry.daemon.cli.Store", return_value=store):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    result = cmd_tree(args)
                    output = mock_stdout.getvalue()

        assert result == 0

        data = json.loads(output)
        assert "job_id" in data
        assert "status" in data
        assert "phases" in data

        # Check phases structure
        assert isinstance(data["phases"], list)
        scout_phase = next((p for p in data["phases"] if p["phase"] == "Scout"), None)
        assert scout_phase is not None
        assert "tasks" in scout_phase
        assert len(scout_phase["tasks"]) == 1


# =============================================================================
# ASCII TREE FORMAT TESTS
# =============================================================================


class TestAsciiTreeFormat:
    """Tests for ASCII tree formatting."""

    def test_ascii_tree_includes_job_header(self, store, sample_job, mock_config):
        """ASCII tree includes job ID and status in header."""
        args = MagicMock()
        args.config = None
        args.job_id = sample_job.id
        args.json = False

        with patch("context_foundry.daemon.cli.Config.load", return_value=mock_config):
            with patch("context_foundry.daemon.cli.Store", return_value=store):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    cmd_tree(args)
                    output = mock_stdout.getvalue()

        # Check header line
        lines = output.strip().split("\n")
        assert len(lines) > 0
        assert "Job" in lines[0]
        assert sample_job.id[:8] in lines[0]

    def test_ascii_tree_phase_hierarchy(
        self, store, sample_job, state_machine, mock_config
    ):
        """ASCII tree shows proper hierarchy with indentation."""
        state_machine.start_job(sample_job.id)
        task = state_machine.create_task_for_phase(sample_job.id, "Scout", 0, 300)
        state_machine.start_task(task.id)

        args = MagicMock()
        args.config = None
        args.job_id = sample_job.id
        args.json = False

        with patch("context_foundry.daemon.cli.Config.load", return_value=mock_config):
            with patch("context_foundry.daemon.cli.Store", return_value=store):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    cmd_tree(args)
                    output = mock_stdout.getvalue()

        # Check for tree structure characters
        assert "+--" in output or "├" in output or "|" in output

    def test_ascii_tree_task_ids(self, store, sample_job, state_machine, mock_config):
        """ASCII tree shows task IDs."""
        state_machine.start_job(sample_job.id)
        task = state_machine.create_task_for_phase(sample_job.id, "Scout", 0, 300)
        state_machine.start_task(task.id)

        args = MagicMock()
        args.config = None
        args.job_id = sample_job.id
        args.json = False

        with patch("context_foundry.daemon.cli.Config.load", return_value=mock_config):
            with patch("context_foundry.daemon.cli.Store", return_value=store):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    cmd_tree(args)
                    output = mock_stdout.getvalue()

        # Task ID should appear (truncated to 8 chars)
        assert task.id[:8] in output


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_tree_job_with_no_tasks(self, store, sample_job, mock_config):
        """cmd_tree handles job with no tasks."""
        args = MagicMock()
        args.config = None
        args.job_id = sample_job.id
        args.json = False

        with patch("context_foundry.daemon.cli.Config.load", return_value=mock_config):
            with patch("context_foundry.daemon.cli.Store", return_value=store):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    result = cmd_tree(args)
                    output = mock_stdout.getvalue()

        assert result == 0
        # Job with no tasks shows no phases (dynamic phase discovery)
        # Output should contain job ID and status but no Phase: lines
        assert sample_job.id[:8] in output

    def test_tree_tasks_across_multiple_phases(
        self, store, sample_job, state_machine, mock_config
    ):
        """cmd_tree shows tasks across multiple phases."""
        state_machine.start_job(sample_job.id)

        # Create tasks in different phases
        scout_task = state_machine.create_task_for_phase(sample_job.id, "Scout", 0, 300)
        state_machine.start_task(scout_task.id)
        state_machine.complete_task(scout_task.id, result={})

        architect_task = state_machine.create_task_for_phase(
            sample_job.id, "Architect", 1, 300
        )
        state_machine.start_task(architect_task.id)

        args = MagicMock()
        args.config = None
        args.job_id = sample_job.id
        args.json = True

        with patch("context_foundry.daemon.cli.Config.load", return_value=mock_config):
            with patch("context_foundry.daemon.cli.Store", return_value=store):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    result = cmd_tree(args)
                    output = mock_stdout.getvalue()

        assert result == 0

        data = json.loads(output)
        scout_phase = next((p for p in data["phases"] if p["phase"] == "Scout"), None)
        architect_phase = next(
            (p for p in data["phases"] if p["phase"] == "Architect"), None
        )
        assert scout_phase is not None
        assert architect_phase is not None
        assert len(scout_phase["tasks"]) == 1
        assert len(architect_phase["tasks"]) == 1
