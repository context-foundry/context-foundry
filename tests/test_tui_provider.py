#!/usr/bin/env python3
"""
Test suite for TUI Data Provider
Tests for get_build_logs functionality
"""

import pytest
import tempfile
import shutil
import json
import asyncio
from pathlib import Path
from datetime import datetime
from tools.tui.data.provider import TUIDataProvider
from tools.tui.config import TUIConfig


class TestTUIDataProvider:
    """Test TUIDataProvider functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        # Create temporary directory for testing
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create test directories
        self.test_build_dir = self.temp_dir / "test_build"
        self.test_build_dir.mkdir()

        self.cf_dir = self.test_build_dir / ".context-foundry"
        self.cf_dir.mkdir()

        # Create test session ID
        self.test_session_id = "test-session-12345"

        # Create minimal TUI config
        self.config = TUIConfig()

        # Create provider instance
        self.provider = TUIDataProvider(self.config)

        # Add test build directory to tracked builds
        self.provider._tracked_builds.append(str(self.test_build_dir))

    def teardown_method(self):
        """Cleanup"""
        if hasattr(self, 'temp_dir') and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_get_build_logs_no_files(self):
        """Test get_build_logs when no log files exist"""
        async def run_test():
            logs = await self.provider.get_build_logs("nonexistent-session")

            assert logs is not None
            assert len(logs) > 0
            assert any("No log files found" in log for log in logs)

        asyncio.run(run_test())

    def test_get_build_logs_with_launch_log(self):
        """Test reading from .launch-{session_id}.log file"""
        # Create a launch log file
        launch_log_path = self.test_build_dir / f".launch-{self.test_session_id}.log"
        launch_log_content = """[INFO] Starting build process
[INFO] Scout phase initiated
[INFO] Architecture phase completed
[INFO] Build successful"""

        launch_log_path.write_text(launch_log_content)

        # Create current-phase.json to help locate the build
        phase_data = {
            "session_id": self.test_session_id,
            "current_phase": "Scout",
            "status": "running"
        }
        phase_file = self.cf_dir / "current-phase.json"
        phase_file.write_text(json.dumps(phase_data))

        async def run_test():
            logs = await self.provider.get_build_logs(self.test_session_id)

            assert logs is not None
            assert len(logs) > 0
            assert "[INFO] Starting build process" in logs
            assert "[INFO] Scout phase initiated" in logs
            assert "[INFO] Architecture phase completed" in logs
            assert "[INFO] Build successful" in logs

        asyncio.run(run_test())

    def test_get_build_logs_with_build_output(self):
        """Test reading from build-output-{session_id}.txt file"""
        # Create a build output file
        build_output_path = self.cf_dir / f"build-output-{self.test_session_id}.txt"
        build_output_content = """================================================================================
STDOUT
================================================================================

Build completed successfully!
All tests passed.
Deployment successful.

================================================================================
STDERR
================================================================================

(empty)
"""

        build_output_path.write_text(build_output_content)

        # Create current-phase.json
        phase_data = {
            "session_id": self.test_session_id,
            "current_phase": "Completed",
            "status": "completed"
        }
        phase_file = self.cf_dir / "current-phase.json"
        phase_file.write_text(json.dumps(phase_data))

        async def run_test():
            logs = await self.provider.get_build_logs(self.test_session_id)

            assert logs is not None
            assert len(logs) > 0
            # The separator only appears if there are prior logs, so just check for content
            assert any("Build completed successfully!" in log for log in logs)
            assert any("All tests passed." in log for log in logs)

        asyncio.run(run_test())

    def test_get_build_logs_with_build_log_md(self):
        """Test reading from build-log.md file"""
        # Create a build-log.md file
        build_log_path = self.cf_dir / "build-log.md"
        build_log_content = """# Build Log: Test Project

## Build Summary

**Mode**: new_project
**Files Modified**: 5
**Build Time**: ~10 minutes

## Changes Made

### File 1: src/main.py
- Added main entry point
- Implemented core logic
- Added error handling
"""

        build_log_path.write_text(build_log_content)

        # Create current-phase.json
        phase_data = {
            "session_id": self.test_session_id,
            "current_phase": "Builder",
            "status": "running"
        }
        phase_file = self.cf_dir / "current-phase.json"
        phase_file.write_text(json.dumps(phase_data))

        async def run_test():
            logs = await self.provider.get_build_logs(self.test_session_id)

            assert logs is not None
            assert len(logs) > 0
            # The separator only appears if there are prior logs, so just check for content
            assert any("Build Log: Test Project" in log for log in logs)
            assert any("Build Summary" in log for log in logs)

        asyncio.run(run_test())

    def test_get_build_logs_with_multiple_sources(self):
        """Test reading from multiple log sources"""
        # Create launch log
        launch_log_path = self.test_build_dir / f".launch-{self.test_session_id}.log"
        launch_log_path.write_text("[INFO] Build started\n[INFO] Initialization complete")

        # Create build output
        build_output_path = self.cf_dir / f"build-output-{self.test_session_id}.txt"
        build_output_path.write_text("Build output here\nTests passed")

        # Create build log
        build_log_path = self.cf_dir / "build-log.md"
        build_log_path.write_text("# Build Log\nImplementation details")

        # Create current-phase.json
        phase_data = {
            "session_id": self.test_session_id,
            "current_phase": "Test",
            "status": "running"
        }
        phase_file = self.cf_dir / "current-phase.json"
        phase_file.write_text(json.dumps(phase_data))

        async def run_test():
            logs = await self.provider.get_build_logs(self.test_session_id)

            assert logs is not None
            assert len(logs) > 0
            # Should contain content from all sources
            assert any("[INFO] Build started" in log for log in logs)
            assert any("BUILD OUTPUT" in log for log in logs)
            assert any("BUILD LOG" in log for log in logs)

        asyncio.run(run_test())

    def test_get_build_logs_caching(self):
        """Test that logs are cached properly"""
        # Create a simple log file
        launch_log_path = self.test_build_dir / f".launch-{self.test_session_id}.log"
        launch_log_path.write_text("[INFO] Initial log entry")

        # Create current-phase.json
        phase_data = {
            "session_id": self.test_session_id,
            "current_phase": "Scout",
            "status": "running"
        }
        phase_file = self.cf_dir / "current-phase.json"
        phase_file.write_text(json.dumps(phase_data))

        async def run_test():
            # First call - should read from file
            logs1 = await self.provider.get_build_logs(self.test_session_id)

            # Modify the file
            launch_log_path.write_text("[INFO] Modified log entry")

            # Second call - should return cached result (within TTL)
            logs2 = await self.provider.get_build_logs(self.test_session_id)

            # Both should be the same (cached)
            assert logs1 == logs2
            assert any("[INFO] Initial log entry" in log for log in logs2)
            assert not any("[INFO] Modified log entry" in log for log in logs2)

        asyncio.run(run_test())

    def test_get_build_logs_handles_json_errors(self):
        """Test that invalid JSON in phase file is handled gracefully"""
        # Create a launch log
        launch_log_path = self.test_build_dir / f".launch-{self.test_session_id}.log"
        launch_log_path.write_text("[INFO] Test log")

        # Create invalid JSON in current-phase.json
        phase_file = self.cf_dir / "current-phase.json"
        phase_file.write_text("{ invalid json }")

        async def run_test():
            # Should not crash, but may not find the build
            logs = await self.provider.get_build_logs(self.test_session_id)

            assert logs is not None
            assert len(logs) > 0

        asyncio.run(run_test())

    def test_get_build_logs_handles_io_errors(self):
        """Test that IO errors are handled gracefully"""
        # Create current-phase.json
        phase_data = {
            "session_id": self.test_session_id,
            "current_phase": "Scout",
            "status": "running"
        }
        phase_file = self.cf_dir / "current-phase.json"
        phase_file.write_text(json.dumps(phase_data))

        # Create a log file that we'll make unreadable
        launch_log_path = self.test_build_dir / f".launch-{self.test_session_id}.log"
        launch_log_path.write_text("[INFO] Test log")

        async def run_test():
            # Make file unreadable (this test may be platform-specific)
            try:
                launch_log_path.chmod(0o000)

                # Should handle the permission error gracefully
                logs = await self.provider.get_build_logs(self.test_session_id)

                assert logs is not None

            finally:
                # Restore permissions for cleanup
                launch_log_path.chmod(0o644)

        asyncio.run(run_test())


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
