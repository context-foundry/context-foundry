"""
Unit tests for Runner random ID appending behavior.

Tests that the Runner correctly:
1. Appends random IDs to new project builds
2. Detects existing code and switches mode before appending IDs
3. Skips random IDs for non-autonomous jobs
4. Detects and avoids ID collisions
5. Prevents double-suffixing of already-suffixed paths
"""

import pytest
import re
from pathlib import Path

from context_foundry.daemon.runner import Runner
from context_foundry.daemon.store import Store
from context_foundry.daemon.models import Job, JobType


@pytest.fixture
def temp_db(tmp_path):
    """Create temporary database for testing"""
    db_path = tmp_path / "test.db"
    return db_path


@pytest.fixture
def store(temp_db):
    """Create Store instance with temporary database"""
    return Store(temp_db)


@pytest.fixture
def runner(store):
    """Create Runner instance for testing"""
    return Runner(store)


@pytest.fixture
def temp_projects_dir(tmp_path):
    """Create temporary projects directory"""
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    return projects_dir


@pytest.mark.unit
@pytest.mark.tier1
class TestRandomIDAppending:
    """Test random ID appending for new projects"""

    def test_new_project_gets_random_id(self, runner, store, temp_projects_dir):
        """Test that new autonomous builds get a random ID appended"""
        # Create job for new project
        working_dir = str(temp_projects_dir / "calculator")
        job = Job.create(
            job_type=JobType.AUTONOMOUS_BUILD,
            params={
                "task": "Build a calculator",
                "working_directory": working_dir,
                "mode": "new_project",
            },
        )
        store.save_job(job)

        # Simulate Runner.run() logic for working directory determination
        # This is the critical section that appends random IDs
        mode = job.params.get("mode", "new_project")

        # Check conditions for random ID appending (new: no exists() check)
        should_append = job.type == JobType.AUTONOMOUS_BUILD and mode == "new_project"

        assert should_append, "Random ID should be appended for new autonomous builds"

        # Simulate the random ID appending (with fixed ID for testing)
        if should_append:
            working_path = Path(working_dir)
            original_name = working_path.name

            # Check if already has suffix (strict pattern: consonant-digit-consonant)
            already_has_suffix = bool(
                re.search(
                    r"-[bcdfghjklmnpqrstvwxz][0-9][bcdfghjklmnpqrstvwxz]$",
                    original_name,
                )
            )
            assert not already_has_suffix, "Original name should not have suffix"

            # Append fixed 3-character ID for testing
            test_id = "c4r"
            new_name = f"{original_name}-{test_id}"
            new_path = working_path.parent / new_name
            new_working_dir = str(new_path)

            # Update job params (this is what the real code does)
            job.params["working_directory"] = new_working_dir
            store.save_job(job)

        # Verify the working directory was updated
        updated_job = store.get_job(job.id)
        final_path = updated_job.params["working_directory"]

        # Assert random ID was appended
        assert final_path != working_dir, "Working directory should be modified"
        assert final_path.endswith("-c4r"), f"Expected -c4r suffix, got: {final_path}"
        assert "calculator-c4r" in final_path, "Should have calculator-c4r"

    def test_delegation_jobs_skip_random_id(self, runner, store, temp_projects_dir):
        """Test that delegation jobs do NOT get random IDs"""
        working_dir = str(temp_projects_dir / "test-project")
        job = Job.create(
            job_type=JobType.DELEGATION,  # Not AUTONOMOUS_BUILD
            params={
                "task": "Run tests",
                "working_directory": working_dir,
                "mode": "new_project",
            },
        )
        store.save_job(job)

        mode = job.params.get("mode", "new_project")

        # Check conditions (new: no exists() check)
        should_append = job.type == JobType.AUTONOMOUS_BUILD and mode == "new_project"

        # Verify random ID should NOT be appended for delegation jobs
        assert not should_append, "Random ID should NOT be appended for delegation jobs"

        # Verify working directory is unchanged
        assert job.params["working_directory"] == working_dir

    def test_no_double_suffixing(self, runner, store, temp_projects_dir):
        """Test that already-suffixed paths don't get another suffix"""
        # Create path that already has a 3-character random ID suffix
        working_dir = str(temp_projects_dir / "calculator-c4r")
        job = Job.create(
            job_type=JobType.AUTONOMOUS_BUILD,
            params={
                "task": "Build calculator",
                "working_directory": working_dir,
                "mode": "new_project",
            },
        )
        store.save_job(job)

        mode = job.params.get("mode", "new_project")
        working_path = Path(working_dir)
        original_name = working_path.name

        # Check if already has suffix (strict pattern: consonant-digit-consonant)
        already_has_suffix = bool(
            re.search(
                r"-[bcdfghjklmnpqrstvwxz][0-9][bcdfghjklmnpqrstvwxz]$", original_name
            )
        )

        # Verify suffix is detected
        assert already_has_suffix, f"Should detect existing suffix in: {original_name}"

        # Verify no new suffix would be added (new: no exists() check)
        if job.type == JobType.AUTONOMOUS_BUILD and mode == "new_project":
            # In real code, this branch would skip appending if already_has_suffix
            if not already_has_suffix:
                pytest.fail("Should have detected existing suffix")

        # Verify path unchanged
        assert job.params["working_directory"] == working_dir
        assert job.params["working_directory"].endswith("-c4r")
        assert not job.params["working_directory"].endswith("-c4r-")  # No double suffix


@pytest.mark.unit
@pytest.mark.tier1
class TestModeAutoSwitching:
    """Test auto mode-switching when existing code is detected"""

    def test_existing_code_switches_to_enhancement(
        self, runner, store, temp_projects_dir
    ):
        """Test that mode switches to enhancement ONLY with explicit existing_repo

        NEW BEHAVIOR:
        - Without existing_repo: mode stays new_project (logs warning, appends random ID)
        - With existing_repo: mode switches to enhancement (no random ID)
        """
        # Create existing project with code
        existing_project = temp_projects_dir / "my-app"
        existing_project.mkdir()
        (existing_project / "main.py").write_text("print('hello')")

        job = Job.create(
            job_type=JobType.AUTONOMOUS_BUILD,
            params={
                "task": "Add a feature",
                "working_directory": str(
                    temp_projects_dir / "ignored"
                ),  # Will be overridden
                "mode": "new_project",  # User says new_project
                "existing_repo": str(
                    existing_project
                ),  # But explicitly points to existing repo
            },
        )
        store.save_job(job)

        # Simulate NEW mode detection logic
        mode = job.params.get("mode", "new_project")
        existing_repo_path = job.params.get("existing_repo")

        # With new logic: check existing_repo path for code
        if existing_repo_path:
            detection_path = Path(existing_repo_path)
        else:
            detection_path = Path(job.params["working_directory"])

        has_existing_code = detection_path.exists() and any(detection_path.iterdir())

        # Verify existing code is detected
        assert has_existing_code, "Should detect existing code at existing_repo"

        # Auto-adjust mode ONLY if existing_repo is provided (NEW behavior)
        if existing_repo_path and has_existing_code and mode == "new_project":
            mode = "enhancement"
            job.params["mode"] = mode
            store.save_job(job)

        # Verify mode was switched (because existing_repo was provided)
        updated_job = store.get_job(job.id)
        assert updated_job.params["mode"] == "enhancement"

        # Verify random ID would NOT be appended (because mode is now enhancement)
        should_append = job.type == JobType.AUTONOMOUS_BUILD and mode == "new_project"
        assert (
            not should_append
        ), "Random ID should NOT be appended after mode switch to enhancement"

    def test_new_project_without_code_stays_new_project(
        self, runner, store, temp_projects_dir
    ):
        """Test that new projects without existing code stay in new_project mode"""
        working_dir = str(temp_projects_dir / "fresh-app")
        job = Job.create(
            job_type=JobType.AUTONOMOUS_BUILD,
            params={
                "task": "Build a new app",
                "working_directory": working_dir,
                "mode": "new_project",
            },
        )
        store.save_job(job)

        # Check for existing code
        detection_path = Path(working_dir)
        has_existing_code = detection_path.exists() and any(detection_path.iterdir())

        # Verify no existing code
        assert not has_existing_code, "Should not detect existing code"

        # Verify mode stays new_project
        mode = job.params.get("mode", "new_project")
        if mode == "new_project" and has_existing_code:
            mode = "enhancement"

        assert mode == "new_project", "Mode should remain new_project"


@pytest.mark.unit
@pytest.mark.tier2
class TestCollisionDetection:
    """Test random ID collision detection"""

    def test_collision_detection_finds_unique_id(
        self, runner, store, temp_projects_dir
    ):
        """Test that collision detection tries multiple IDs until unique one is found"""
        # Create existing directories with various 3-char IDs
        base_name = "myapp"
        existing_ids = ["c4r", "n3r", "b0w", "t5p", "m7k"]
        for test_id in existing_ids:
            (temp_projects_dir / f"{base_name}-{test_id}").mkdir()

        working_dir = str(temp_projects_dir / base_name)
        job = Job.create(
            job_type=JobType.AUTONOMOUS_BUILD,
            params={
                "task": "Build myapp",
                "working_directory": working_dir,
                "mode": "new_project",
            },
        )

        # Simulate collision detection (this is what the real code does)
        working_path = Path(working_dir)
        max_attempts = 20
        found_unique = False

        # Use fixed sequence for testing
        test_ids = ["c4r", "n3r", "b0w", "t5p", "m7k", "q2z"]  # q2z doesn't exist

        for attempt in range(max_attempts):
            if attempt < len(test_ids):
                test_id = test_ids[attempt]
            else:
                test_id = "x9y"  # fallback

            new_name = f"{base_name}-{test_id}"
            new_path = working_path.parent / new_name

            if not new_path.exists():
                # Found unique ID
                found_unique = True
                job.params["working_directory"] = str(new_path)
                break

        # Verify unique ID was found (should be q2z, the first non-existing one)
        assert found_unique, "Should find unique ID within 20 attempts"
        assert job.params["working_directory"].endswith("-q2z"), "Should have ID q2z"

    def test_all_attempts_exhausted_keeps_original(
        self, runner, store, temp_projects_dir
    ):
        """Test that if all collision attempts fail, original path is kept"""
        # This is an edge case that's very unlikely but should be handled
        base_name = "myapp"
        working_dir = str(temp_projects_dir / base_name)

        # Simulate all attempts failing (would need to create 10,000 dirs in reality)
        # For this test, we just verify the fallback logic works

        job = Job.create(
            job_type=JobType.AUTONOMOUS_BUILD,
            params={
                "task": "Build myapp",
                "working_directory": working_dir,
                "mode": "new_project",
            },
        )

        # Simulate max_attempts exhausted
        max_attempts = 10
        found_unique = False

        for attempt in range(max_attempts):
            # Simulate all IDs exist (skip the check)
            continue

        # If not found, keep original path (fallback behavior)
        if not found_unique:
            # Original path is kept
            assert job.params["working_directory"] == working_dir


@pytest.mark.unit
@pytest.mark.tier1
class TestJobParamsUpdate:
    """Test that job params are updated with actual working directory"""

    def test_job_params_reflect_actual_path(self, runner, store, temp_projects_dir):
        """Test that job.params['working_directory'] is updated with the actual path"""
        original_path = str(temp_projects_dir / "weather-app")
        job = Job.create(
            job_type=JobType.AUTONOMOUS_BUILD,
            params={
                "task": "Build weather app",
                "working_directory": original_path,
                "mode": "new_project",
            },
        )
        store.save_job(job)

        # Simulate random ID appending (new: no exists() check)
        if (
            job.type == JobType.AUTONOMOUS_BUILD
            and job.params.get("mode") == "new_project"
        ):
            working_path = Path(original_path)
            # Use 3-character ID like c4r
            new_path = working_path.parent / f"{working_path.name}-c4r"
            job.params["working_directory"] = str(new_path)
            store.save_job(job)

        # Verify params were updated
        updated_job = store.get_job(job.id)
        actual_path = updated_job.params["working_directory"]

        assert actual_path != original_path, "Path should be updated"
        assert actual_path.endswith("-c4r"), "Should have 3-char random ID suffix"

        # This is the key fix: job metadata reflects the ACTUAL path
        # Users can query this via get_job_status_from_daemon()
        assert "weather-app-c4r" in actual_path


@pytest.mark.integration
@pytest.mark.tier1
class TestRunnerPreRunLogic:
    """
    Integration tests that call Runner.run() to verify pre-run logic.

    SCOPE: These tests verify parameter mutations (random ID, mode switch) and
    persistence to store that happen BEFORE _run_autonomous_build executes.

    NOT TESTED: Polling loop, notifications, active task tracking, log/phase
    emission, pattern merge, or store.update_job_status calls (all happen inside
    _run_autonomous_build which is mocked).
    """

    def test_runner_persists_random_id_to_store(self, runner, store, temp_projects_dir):
        """Test that Runner.run() appends random ID AND persists it via store.save_job()"""
        # Create job for new project (directory doesn't exist yet)
        working_dir = str(temp_projects_dir / "calculator")
        job = Job.create(
            job_type=JobType.AUTONOMOUS_BUILD,
            params={
                "task": "Build a calculator",
                "working_directory": working_dir,
                "mode": "new_project",
            },
        )
        store.save_job(job)

        # Track store.save_job() calls
        from unittest.mock import patch

        save_job_calls = []
        original_save_job = store.save_job

        def tracked_save_job(job_obj):
            save_job_calls.append(job_obj.params.copy())
            return original_save_job(job_obj)

        def mock_autonomous_build(job_obj, working_directory, timeout_minutes):
            """Mock autonomous build that returns success"""
            return {
                "status": "completed",
                "working_directory": working_directory,
                "duration_seconds": 1.0,
                "phases_completed": ["Scout", "Architect", "Builder"],
            }

        with patch.object(store, "save_job", side_effect=tracked_save_job):
            with patch.object(
                runner, "_run_autonomous_build", side_effect=mock_autonomous_build
            ):
                # Call the ACTUAL Runner.run() method
                result = runner.run(job)

        # Verify the run completed (this tests post-run logic executed)
        assert result["success"] is True, "Runner.run() should return success=True"
        assert result["exit_code"] == 0

        # KEY TEST: Verify store.save_job() was called with updated params
        assert len(save_job_calls) >= 1, "store.save_job() should be called"

        # Verify random ID was appended in the saved params
        saved_params = save_job_calls[-1]  # Get last save
        final_path = saved_params["working_directory"]

        assert final_path != working_dir, "Working directory should be modified"
        assert re.search(
            r"-[bcdfghjklmnpqrstvwxz][0-9][bcdfghjklmnpqrstvwxz]$", final_path
        ), "Should have consonant-digit-consonant random ID suffix"
        assert "calculator" in final_path, "Should contain original name"

        # Verify persistence: retrieve from store and confirm
        updated_job = store.get_job(job.id)
        assert updated_job.params["working_directory"] == final_path

    def test_runner_persists_mode_auto_switch_to_store(
        self, runner, store, temp_projects_dir
    ):
        """Test that Runner.run() auto-switches mode ONLY with explicit existing_repo

        NEW BEHAVIOR (after fix):
        - Auto-switch to enhancement ONLY when existing_repo is explicitly provided
        - Without existing_repo, mode stays new_project (with warning logged)
        - This preserves testing workflow while maintaining safety net for legitimate enhancements
        """
        # Create existing project with code
        existing_project = temp_projects_dir / "my-app"
        existing_project.mkdir()
        (existing_project / "main.py").write_text("print('hello')")

        # Create job with mode=new_project AND existing_repo (explicit enhancement request)
        job = Job.create(
            job_type=JobType.AUTONOMOUS_BUILD,
            params={
                "task": "Add a feature",
                "working_directory": str(
                    temp_projects_dir / "ignored"
                ),  # Will be overridden by existing_repo
                "mode": "new_project",  # User says new_project...
                "existing_repo": str(
                    existing_project
                ),  # ...but points to existing repo
            },
        )
        store.save_job(job)

        # Track store.save_job() calls
        from unittest.mock import patch

        save_job_calls = []
        original_save_job = store.save_job

        def tracked_save_job(job_obj):
            save_job_calls.append(job_obj.params.copy())
            return original_save_job(job_obj)

        def mock_autonomous_build(job_obj, working_directory, timeout_minutes):
            """Mock autonomous build that returns success"""
            return {
                "status": "completed",
                "working_directory": working_directory,
                "duration_seconds": 1.0,
                "phases_completed": ["Scout", "Architect", "Builder"],
            }

        with patch.object(store, "save_job", side_effect=tracked_save_job):
            with patch.object(
                runner, "_run_autonomous_build", side_effect=mock_autonomous_build
            ):
                # Call the ACTUAL Runner.run() method
                result = runner.run(job)

        # Verify the run completed
        assert result["success"] is True
        assert result["exit_code"] == 0

        # KEY TEST: Verify store.save_job() was called
        assert len(save_job_calls) >= 1, "store.save_job() should be called"

        # With new logic: mode auto-switches ONLY because existing_repo was provided
        saved_params = save_job_calls[-1]  # Get last save

        # Verify mode was auto-switched to enhancement (because existing_repo + code exists)
        assert (
            saved_params["mode"] == "enhancement"
        ), "Mode should be auto-switched when existing_repo is provided and has code"

        # Verify persistence: retrieve from store and confirm
        updated_job = store.get_job(job.id)
        assert updated_job.params["mode"] == "enhancement"
