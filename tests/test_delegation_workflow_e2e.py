#!/usr/bin/env python3
"""
End-to-end integration tests for MCP Delegation workflows.

Tests complete delegation workflows:
- Synchronous delegation: Request → Claude spawn → Execution → Result
- Asynchronous delegation: Request → Task ID → Background execution → Result retrieval
- Multi-phase builds: Scout → Architect → Builder → Test → Deploy
- Task lifecycle management and monitoring
- Error recovery and timeout handling

Priority: 10/10 - Core MCP delegation functionality
"""

import pytest
import tempfile
import shutil
import json
import time
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Mock FastMCP before importing
import sys


# Create a proper FastMCP mock that returns pass-through decorators
class MockFastMCP:
    def __init__(self, *args, **kwargs):
        pass

    def tool(self, *args, **kwargs):
        """Decorator that returns the original function unchanged"""

        def decorator(func):
            return func

        return decorator

    def resource(self, *args, **kwargs):
        """Decorator that returns the original function unchanged"""

        def decorator(func):
            return func

        return decorator


mock_module = MagicMock()
mock_module.FastMCP = MockFastMCP
mock_module.Context = MagicMock

sys.modules["fastmcp"] = mock_module
sys.modules["fastmcp.server"] = MagicMock()
sys.modules["fastmcp.server.dependencies"] = MagicMock()
sys.modules["fastmcp.server.dependencies"].get_context = MagicMock()

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))


@pytest.fixture(scope="function", autouse=True)
def reload_mcp_server():
    """Force reload of mcp_server module before each test to ensure mocks are applied"""
    if "mcp_server" in sys.modules:
        del sys.modules["mcp_server"]
    yield
    # Cleanup after test
    if "mcp_server" in sys.modules:
        del sys.modules["mcp_server"]


@pytest.mark.integration
@pytest.mark.tier1
class TestSynchronousDelegationE2E:
    """End-to-end tests for synchronous delegation workflows"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_project_dir = Path(self.temp_dir) / "test_project"
        self.test_project_dir.mkdir()

    def teardown_method(self):
        """Cleanup"""
        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_simple_delegation_workflow(self):
        """Test complete simple delegation workflow"""
        with patch("subprocess.run") as mock_run:
            # Mock successful Claude Code execution
            mock_run.return_value = Mock(
                returncode=0,
                stdout="File created successfully: hello.py\nTests passed: 3/3\n",
                stderr="",
            )

            # Import AFTER patching subprocess
            from mcp_server import delegate_to_claude_code

            # Execute delegation
            result = delegate_to_claude_code(
                task="Create a simple hello world Python script with tests",
                working_directory=str(self.test_project_dir),
            )

            # Verify subprocess was called with correct parameters
            mock_run.assert_called_once()
            call_args = mock_run.call_args

            # Verify command structure
            cmd = call_args[0][0]
            assert "claude" in cmd
            assert "--print" in cmd
            assert "Create a simple hello world Python script with tests" in cmd

            # Verify working directory
            assert call_args[1]["cwd"] == str(self.test_project_dir)

            # Verify result format
            assert "✅" in result or "Success" in result
            assert "hello.py" in result

    def test_delegation_with_file_output(self):
        """Test delegation that writes files and outputs results"""
        with patch("subprocess.run") as mock_run:
            # Simulate Claude creating files
            test_file = self.test_project_dir / "created_file.txt"
            test_file.write_text("Content created by Claude Code")

            mock_run.return_value = Mock(
                returncode=0,
                stdout=f"Created file: {test_file}\nContent written successfully\n",
                stderr="",
            )

            from mcp_server import delegate_to_claude_code

            result = delegate_to_claude_code(
                task="Create a text file with sample content",
                working_directory=str(self.test_project_dir),
            )

            # Verify file was created (in real scenario)
            assert test_file.exists()
            assert test_file.read_text() == "Content created by Claude Code"

            # Verify result contains success message
            assert "✅" in result or "Success" in result

    def test_delegation_with_error_recovery(self):
        """Test delegation error handling and recovery"""
        with patch("subprocess.run") as mock_run:
            # First call fails, second succeeds
            mock_run.side_effect = [
                Mock(returncode=1, stdout="", stderr="Error: Missing dependency"),
                Mock(
                    returncode=0,
                    stdout="Dependency installed\nTask completed\n",
                    stderr="",
                ),
            ]

            from mcp_server import delegate_to_claude_code

            # First attempt fails
            result1 = delegate_to_claude_code(
                task="Run tests", working_directory=str(self.test_project_dir)
            )
            assert "❌" in result1 or "Error" in result1

            # Second attempt succeeds
            result2 = delegate_to_claude_code(
                task="Install dependencies and run tests",
                working_directory=str(self.test_project_dir),
            )
            assert "✅" in result2 or "Success" in result2

    def test_delegation_timeout_workflow(self):
        """Test complete timeout handling workflow"""
        import subprocess

        with patch("subprocess.run") as mock_run:
            # Mock timeout exception
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["claude", "--print", "Long task"], timeout=300
            )

            from mcp_server import delegate_to_claude_code

            result = delegate_to_claude_code(
                task="Long running analysis task", timeout_minutes=5.0
            )

            # Verify timeout was handled gracefully
            assert "⏱️" in result or "Timeout" in result or "timeout" in result.lower()
            assert "5" in result  # timeout duration


@pytest.mark.integration
@pytest.mark.tier1
class TestAsynchronousDelegationE2E:
    """End-to-end tests for asynchronous delegation workflows"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_project_dir = Path(self.temp_dir) / "async_project"
        self.test_project_dir.mkdir()

        # Clear active tasks
        from mcp_server import active_tasks

        active_tasks.clear()

    def teardown_method(self):
        """Cleanup"""
        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_async_delegation_lifecycle(self):
        """Test complete async task lifecycle: start → monitor → complete"""
        with patch("subprocess.Popen") as mock_popen:
            # Mock process
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None  # Running
            mock_process.stdout = Mock()
            mock_process.stderr = Mock()
            mock_process.stdout.read.return_value = b"Task in progress...\n"
            mock_process.stderr.read.return_value = b""
            mock_popen.return_value = mock_process

            from mcp_server import (
                delegate_to_claude_code_async,
                get_delegation_result,
                active_tasks,
            )

            # Step 1: Start async task
            result = delegate_to_claude_code_async(
                task="Build and test application",
                working_directory=str(self.test_project_dir),
            )

            # Extract task ID from result
            assert "task" in result.lower() or "id" in result.lower()
            task_ids = list(active_tasks.keys())
            assert len(task_ids) > 0
            task_id = task_ids[0]

            # Step 2: Monitor running task
            status = get_delegation_result(task_id=task_id)
            assert "running" in status.lower() or "⏳" in status

            # Step 3: Simulate task completion
            mock_process.poll.return_value = 0  # Completed
            mock_process.stdout.read.return_value = (
                b"Build successful\nAll tests passed\n"
            )

            # Manually update task status (simulating background completion)
            if task_id in active_tasks:
                active_tasks[task_id]["status"] = "completed"
                active_tasks[task_id]["duration"] = 5.2  # Add duration field
                active_tasks[task_id]["exit_code"] = 0  # Add exit code
                active_tasks[task_id]["result"] = {
                    "returncode": 0,
                    "stdout": "Build successful\nAll tests passed\n",
                    "stderr": "",
                }

            # Step 4: Retrieve completed result
            final_result = get_delegation_result(task_id=task_id)
            assert "completed" in final_result.lower() or "✅" in final_result
            assert 'exit_code": 0' in final_result  # Verify successful exit code

    @patch("subprocess.Popen")
    def test_multiple_concurrent_async_tasks(self, mock_popen):
        """Test handling multiple concurrent async delegations"""
        from mcp_server import (
            delegate_to_claude_code_async,
            list_delegations,
            active_tasks,
        )

        # Create mock processes
        mock_processes = []
        for i in range(3):
            mock_proc = Mock()
            mock_proc.pid = 10000 + i
            mock_proc.poll.return_value = None  # Running
            mock_processes.append(mock_proc)

        mock_popen.side_effect = mock_processes

        # Start 3 concurrent tasks
        task_ids = []
        for i in range(3):
            delegate_to_claude_code_async(
                task=f"Task {i}: Build component {i}",
                working_directory=str(self.test_project_dir),
            )
            # Get the last added task ID
            current_ids = list(active_tasks.keys())
            new_id = [tid for tid in current_ids if tid not in task_ids]
            if new_id:
                task_ids.append(new_id[0])

        # Verify all tasks are tracked
        assert len(task_ids) == 3

        # List all delegations
        delegation_list = list_delegations()

        # Verify list contains all task IDs
        for task_id in task_ids:
            assert task_id in delegation_list

    @patch("subprocess.Popen")
    def test_async_task_failure_handling(self, mock_popen):
        """Test async task failure handling"""
        from mcp_server import (
            delegate_to_claude_code_async,
            get_delegation_result,
            active_tasks,
        )

        # Mock failed process
        mock_process = Mock()
        mock_process.pid = 99999
        mock_process.poll.return_value = 1  # Failed
        mock_process.stdout = Mock()
        mock_process.stderr = Mock()
        mock_process.stdout.read.return_value = b""
        mock_process.stderr.read.return_value = b"Error: Build failed\n"
        mock_popen.return_value = mock_process

        # Start task
        delegate_to_claude_code_async(
            task="Task that will fail", working_directory=str(self.test_project_dir)
        )

        task_id = list(active_tasks.keys())[0]

        # Simulate failure
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["result"] = {
            "returncode": 1,
            "stdout": "",
            "stderr": "Error: Build failed\n",
        }

        # Get result
        final_result = get_delegation_result(task_id=task_id)

        # Verify failure is reported
        assert "failed" in final_result.lower() or "❌" in final_result
        assert "error" in final_result.lower() or "Build failed" in final_result


@pytest.mark.integration
@pytest.mark.tier1
class TestMultiPhaseBuildWorkflow:
    """Test complete multi-phase build workflows"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.build_dir = Path(self.temp_dir) / "build_project"
        self.build_dir.mkdir()
        self.context_foundry_dir = self.build_dir / ".context-foundry"
        self.context_foundry_dir.mkdir()

    def teardown_method(self):
        """Cleanup"""
        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def _create_phase_file(self, phase_name, progress=0, status="running"):
        """Helper to create phase tracking file"""
        phase_file = self.context_foundry_dir / "current-phase.json"
        phase_data = {
            "phase": phase_name,
            "progress": progress,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }
        phase_file.write_text(json.dumps(phase_data, indent=2))

    @patch("subprocess.run")
    def test_seven_phase_build_workflow(self, mock_run):
        """Test complete 7-phase autonomous build workflow"""
        # Mock successful execution for each phase
        phase_outputs = {
            "Scout": "Scout Report:\n- Requirements analyzed\n- Tech stack: Python + FastAPI\n",
            "Architect": "Architecture:\n- API endpoints designed\n- Database schema created\n",
            "Builder": "Build complete:\n- All files created\n- Code implemented\n",
            "Test": "Testing:\n- 15 tests written\n- All tests passing\n",
            "Screenshot": "Screenshots captured:\n- Homepage.png\n- Dashboard.png\n",
            "Documentation": "Documentation:\n- README.md created\n- API docs generated\n",
            "Deploy": "Deployment:\n- GitHub repo created\n- Code pushed successfully\n",
        }

        mock_run.side_effect = [
            Mock(returncode=0, stdout=output, stderr="")
            for output in phase_outputs.values()
        ]

        from mcp_server import delegate_to_claude_code

        phases = [
            "Scout",
            "Architect",
            "Builder",
            "Test",
            "Screenshot",
            "Documentation",
            "Deploy",
        ]
        results = {}

        # Execute each phase
        for phase in phases:
            # Create phase file to simulate phase tracking
            self._create_phase_file(phase, progress=0, status="running")

            # Execute phase
            result = delegate_to_claude_code(
                task=f"Execute {phase} phase for todo app",
                working_directory=str(self.build_dir),
            )

            results[phase] = result

            # Verify phase completed successfully
            assert "✅" in result or "Success" in result
            assert phase_outputs[phase].split(":")[0] in result or phase in result

            # Mark phase as complete
            self._create_phase_file(phase, progress=100, status="completed")

        # Verify all phases completed
        assert len(results) == 7
        for phase, result in results.items():
            assert "✅" in result or "Success" in result

    @patch("subprocess.run")
    def test_phase_failure_and_recovery(self, mock_run):
        """Test phase failure and recovery workflow"""
        from mcp_server import delegate_to_claude_code

        # First attempt: Test phase fails
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Scout completed\n", stderr=""),  # Scout succeeds
            Mock(
                returncode=0, stdout="Architecture ready\n", stderr=""
            ),  # Architect succeeds
            Mock(
                returncode=0, stdout="Build completed\n", stderr=""
            ),  # Builder succeeds
            Mock(
                returncode=1, stdout="", stderr="Test phase failed: Import error\n"
            ),  # Test fails
            Mock(
                returncode=0, stdout="Tests fixed and passing\n", stderr=""
            ),  # Test retry succeeds
        ]

        # Execute phases until failure
        self._create_phase_file("Scout")
        scout_result = delegate_to_claude_code(
            task="Scout phase", working_directory=str(self.build_dir)
        )
        assert "✅" in scout_result or "Success" in scout_result

        self._create_phase_file("Architect")
        architect_result = delegate_to_claude_code(
            task="Architect phase", working_directory=str(self.build_dir)
        )
        assert "✅" in architect_result or "Success" in architect_result

        self._create_phase_file("Builder")
        builder_result = delegate_to_claude_code(
            task="Builder phase", working_directory=str(self.build_dir)
        )
        assert "✅" in builder_result or "Success" in builder_result

        # Test phase fails
        self._create_phase_file("Test")
        test_result = delegate_to_claude_code(
            task="Test phase", working_directory=str(self.build_dir)
        )
        assert "❌" in test_result or "Error" in test_result

        # Retry test phase
        test_retry_result = delegate_to_claude_code(
            task="Fix and retry test phase", working_directory=str(self.build_dir)
        )
        assert "✅" in test_retry_result or "Success" in test_retry_result

    @patch("subprocess.run")
    def test_phase_progress_tracking(self, mock_run):
        """Test phase progress tracking throughout build"""
        mock_run.return_value = Mock(
            returncode=0, stdout="Phase in progress...\n", stderr=""
        )

        # Simulate phase with progress updates
        phases_progress = [
            ("Scout", 0),
            ("Scout", 50),
            ("Scout", 100),
            ("Architect", 0),
            ("Architect", 100),
        ]

        for phase, progress in phases_progress:
            # Update phase file
            self._create_phase_file(phase, progress=progress)

            # Verify file was created correctly
            phase_file = self.context_foundry_dir / "current-phase.json"
            assert phase_file.exists()

            phase_data = json.loads(phase_file.read_text())
            assert phase_data["phase"] == phase
            assert phase_data["progress"] == progress


@pytest.mark.integration
@pytest.mark.tier2
class TestDelegationEdgeCases:
    """Test edge cases and error conditions in delegation"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Cleanup"""
        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    @patch("subprocess.run")
    def test_delegation_with_special_characters(self, mock_run):
        """Test delegation with special characters in task"""
        mock_run.return_value = Mock(returncode=0, stdout="Task completed\n", stderr="")

        from mcp_server import delegate_to_claude_code

        # Task with special characters
        task = 'Create file with name: "test\'s_file-2024.txt" & check $PATH'

        result = delegate_to_claude_code(
            task=task, working_directory=str(self.temp_dir)
        )

        # Verify task was executed
        assert "✅" in result or "Success" in result

    @patch("subprocess.run")
    def test_delegation_with_very_long_output(self, mock_run):
        """Test delegation with extremely large output"""
        # Create 100KB+ output
        large_output = "\n".join([f"Line {i}: " + "x" * 100 for i in range(1000)])

        mock_run.return_value = Mock(returncode=0, stdout=large_output, stderr="")

        from mcp_server import delegate_to_claude_code

        result = delegate_to_claude_code(
            task="Generate large output",
            working_directory=str(self.temp_dir),
            include_full_output=False,  # Should truncate
        )

        # Output should be truncated to reasonable size
        # Typically < 40KB to stay under token limits
        assert len(result) < len(large_output)

    @patch("subprocess.run")
    def test_delegation_empty_working_directory(self, mock_run):
        """Test delegation with no working directory specified"""
        mock_run.return_value = Mock(
            returncode=0, stdout="Task completed in current directory\n", stderr=""
        )

        from mcp_server import delegate_to_claude_code

        # No working directory specified - should use current dir
        result = delegate_to_claude_code(task="Simple task")

        # Should still work
        assert "✅" in result or "Success" in result

    def test_delegation_nonexistent_directory(self):
        """Test delegation with nonexistent working directory"""
        from mcp_server import delegate_to_claude_code

        result = delegate_to_claude_code(
            task="Test task", working_directory="/totally/nonexistent/path/12345"
        )

        # Should return error without attempting execution
        assert (
            "❌" in result or "error" in result.lower() or "not exist" in result.lower()
        )


@pytest.mark.integration
@pytest.mark.tier2
class TestDelegationPerformance:
    """Test delegation performance and optimization"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Cleanup"""
        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    @patch("subprocess.run")
    def test_delegation_execution_timing(self, mock_run):
        """Test that delegation timing is tracked"""
        # Simulate 2-second execution
        mock_run.return_value = Mock(returncode=0, stdout="Task completed\n", stderr="")

        from mcp_server import delegate_to_claude_code
        import time

        start = time.time()
        delegate_to_claude_code(task="Timed task", working_directory=str(self.temp_dir))
        duration = time.time() - start

        # Should complete quickly (mocked)
        assert duration < 1.0  # Should be nearly instant with mock

    @patch("subprocess.Popen")
    def test_async_delegation_immediate_return(self, mock_popen):
        """Test that async delegation returns immediately"""
        from mcp_server import delegate_to_claude_code_async, active_tasks

        mock_process = Mock()
        mock_process.pid = 11111
        mock_popen.return_value = mock_process

        active_tasks.clear()

        start = time.time()
        result = delegate_to_claude_code_async(
            task="Background task", working_directory=str(self.temp_dir)
        )
        duration = time.time() - start

        # Should return immediately (< 0.1s)
        assert duration < 0.1
        assert "task" in result.lower() or "background" in result.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
