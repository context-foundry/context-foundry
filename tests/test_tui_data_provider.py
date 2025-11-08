"""Tests for TUI data provider"""

import asyncio
import json
import tempfile
from pathlib import Path
from datetime import datetime
import pytest

from tools.tui.data.provider import TUIDataProvider
from tools.tui.config import TUIConfig


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config(temp_dir):
    """Create a test configuration"""
    return TUIConfig(
        context_foundry_dir=temp_dir / ".context-foundry",
        update_interval_seconds=1.0,
        max_log_lines=100
    )


@pytest.fixture
def provider(config):
    """Create a TUI data provider"""
    return TUIDataProvider(config)


@pytest.mark.asyncio
async def test_get_build_logs_with_launch_log(temp_dir, provider):
    """Test reading logs from .launch-{session_id}.log file"""
    session_id = "test-session-123"

    # Create a test build directory with current-phase.json
    build_dir = temp_dir / "test-build"
    build_dir.mkdir(parents=True)
    cf_dir = build_dir / ".context-foundry"
    cf_dir.mkdir(parents=True)

    # Create current-phase.json
    phase_data = {
        "session_id": session_id,
        "current_phase": "Scout",
        "phase_number": "1/7",
        "status": "running",
        "progress_detail": "Analyzing requirements",
        "test_iteration": 0,
        "phases_completed": [],
        "started_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat()
    }
    phase_file = cf_dir / "current-phase.json"
    with open(phase_file, 'w') as f:
        json.dump(phase_data, f)

    # Create launch log file
    launch_log = build_dir / f".launch-{session_id}.log"
    log_content = """[INFO] Starting build...
[INFO] Scout phase: Analyzing requirements
[INFO] Found 10 source files
[INFO] Generating report..."""

    with open(launch_log, 'w') as f:
        f.write(log_content)

    # Add to tracked builds
    provider._tracked_builds.append(str(build_dir))

    # Get logs
    logs = await provider.get_build_logs(session_id)

    # Verify logs were read correctly
    assert len(logs) > 0
    assert any(f".launch-{session_id}.log" in log for log in logs)
    assert any("Starting build" in log for log in logs)
    assert any("Scout phase" in log for log in logs)


@pytest.mark.asyncio
async def test_get_build_logs_with_phase_logs(temp_dir, provider):
    """Test reading logs from .context-foundry/*.log files"""
    session_id = "test-session-456"

    # Create a test build directory
    build_dir = temp_dir / "test-build"
    build_dir.mkdir(parents=True)
    cf_dir = build_dir / ".context-foundry"
    cf_dir.mkdir(parents=True)

    # Create current-phase.json
    phase_data = {
        "session_id": session_id,
        "current_phase": "Architect",
        "phase_number": "2/7",
        "status": "running",
        "progress_detail": "Designing system",
        "test_iteration": 0,
        "phases_completed": ["Scout"],
        "started_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat()
    }
    phase_file = cf_dir / "current-phase.json"
    with open(phase_file, 'w') as f:
        json.dump(phase_data, f)

    # Create phase-specific log files
    scout_log = cf_dir / "scout.log"
    scout_log.write_text("""[INFO] Scout phase started
[INFO] Analyzing codebase structure
[INFO] Found 5 modules""")

    architect_log = cf_dir / "architect.log"
    architect_log.write_text("""[INFO] Architect phase started
[INFO] Designing system architecture
[INFO] Creating component diagram""")

    # Add to tracked builds
    provider._tracked_builds.append(str(build_dir))

    # Get logs
    logs = await provider.get_build_logs(session_id)

    # Verify logs were read correctly
    assert len(logs) > 0
    assert any("scout.log" in log for log in logs)
    assert any("architect.log" in log for log in logs)
    assert any("Scout phase started" in log for log in logs)
    assert any("Architect phase started" in log for log in logs)


@pytest.mark.asyncio
async def test_get_build_logs_session_not_found(provider):
    """Test handling of non-existent session"""
    session_id = "nonexistent-session"

    # Get logs for non-existent session
    logs = await provider.get_build_logs(session_id)

    # Should return warning message
    assert len(logs) > 0
    assert any("No logs found" in log for log in logs)


@pytest.mark.asyncio
async def test_get_build_logs_no_log_files(temp_dir, provider):
    """Test handling when session exists but no log files present"""
    session_id = "test-session-789"

    # Create a test build directory without log files
    build_dir = temp_dir / "test-build"
    build_dir.mkdir(parents=True)
    cf_dir = build_dir / ".context-foundry"
    cf_dir.mkdir(parents=True)

    # Create current-phase.json
    phase_data = {
        "session_id": session_id,
        "current_phase": "Builder",
        "phase_number": "3/7",
        "status": "running",
        "progress_detail": "Building code",
        "test_iteration": 0,
        "phases_completed": ["Scout", "Architect"],
        "started_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat()
    }
    phase_file = cf_dir / "current-phase.json"
    with open(phase_file, 'w') as f:
        json.dump(phase_data, f)

    # Add to tracked builds
    provider._tracked_builds.append(str(build_dir))

    # Get logs
    logs = await provider.get_build_logs(session_id)

    # Should return informative message
    assert len(logs) > 0
    assert any("No log files found" in log for log in logs)
    assert any(str(build_dir) in log for log in logs)


@pytest.mark.asyncio
async def test_get_build_logs_caching(temp_dir, provider):
    """Test that logs are properly cached"""
    session_id = "test-session-cache"

    # Create a test build directory
    build_dir = temp_dir / "test-build"
    build_dir.mkdir(parents=True)
    cf_dir = build_dir / ".context-foundry"
    cf_dir.mkdir(parents=True)

    # Create current-phase.json
    phase_data = {
        "session_id": session_id,
        "current_phase": "Scout",
        "phase_number": "1/7",
        "status": "running",
        "progress_detail": "Analyzing",
        "test_iteration": 0,
        "phases_completed": [],
        "started_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat()
    }
    phase_file = cf_dir / "current-phase.json"
    with open(phase_file, 'w') as f:
        json.dump(phase_data, f)

    # Create launch log
    launch_log = build_dir / f".launch-{session_id}.log"
    launch_log.write_text("[INFO] Initial log content")

    # Add to tracked builds
    provider._tracked_builds.append(str(build_dir))

    # Get logs first time
    logs1 = await provider.get_build_logs(session_id)

    # Modify log file
    launch_log.write_text("[INFO] Modified log content")

    # Get logs second time (should be cached)
    logs2 = await provider.get_build_logs(session_id)

    # Should be the same (cached)
    assert logs1 == logs2
    assert any("Initial log content" in log for log in logs2)
    assert not any("Modified log content" in log for log in logs2)


@pytest.mark.asyncio
async def test_get_build_logs_encoding_error_handling(temp_dir, provider):
    """Test handling of files with encoding issues"""
    session_id = "test-session-encoding"

    # Create a test build directory
    build_dir = temp_dir / "test-build"
    build_dir.mkdir(parents=True)
    cf_dir = build_dir / ".context-foundry"
    cf_dir.mkdir(parents=True)

    # Create current-phase.json
    phase_data = {
        "session_id": session_id,
        "current_phase": "Scout",
        "phase_number": "1/7",
        "status": "running",
        "progress_detail": "Analyzing",
        "test_iteration": 0,
        "phases_completed": [],
        "started_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat()
    }
    phase_file = cf_dir / "current-phase.json"
    with open(phase_file, 'w') as f:
        json.dump(phase_data, f)

    # Create a log file with mixed content (some valid, some with encoding issues)
    launch_log = build_dir / f".launch-{session_id}.log"
    with open(launch_log, 'wb') as f:
        # Write some valid UTF-8
        f.write(b"[INFO] Valid log line\n")
        # Write some invalid bytes (these should be handled with errors='replace')
        f.write(b"[INFO] Invalid bytes: \xff\xfe\n")
        # More valid content
        f.write(b"[INFO] Another valid line\n")

    # Add to tracked builds
    provider._tracked_builds.append(str(build_dir))

    # Get logs - should handle encoding errors gracefully
    logs = await provider.get_build_logs(session_id)

    # Should have successfully read the file
    assert len(logs) > 0
    assert any("Valid log line" in log for log in logs)
    assert any("Another valid line" in log for log in logs)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
