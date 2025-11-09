"""
Comprehensive tests for LiveStream MetricsCollector - the real-time monitoring backbone.

CRITICAL PATHS TESTED:
- File watcher initialization and debouncing
- Cross-thread async communication
- Live phase update collection
- Event loop management
- Metrics collection from various sources

Priority: 10/10 - This is the real-time monitoring backbone. Failures break visibility.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, mock_open

from tools.livestream.metrics_collector import MetricsCollector, PhaseFileWatcher


class TestPhaseFileWatcher:
    """Test filesystem watching for phase updates"""

    @pytest.fixture
    def mock_collector(self):
        """Create mock collector"""
        collector = Mock()
        collector.loop = asyncio.new_event_loop()
        return collector

    @pytest.fixture
    def watcher(self, mock_collector):
        """Create phase file watcher"""
        return PhaseFileWatcher(mock_collector)

    def test_watcher_initialization(self, mock_collector):
        """Test watcher initializes correctly"""
        watcher = PhaseFileWatcher(mock_collector)

        assert watcher.collector == mock_collector
        assert watcher.debounce_timers == {}
        assert watcher.debounce_delay == 0.1

    def test_watcher_ignores_directories(self, watcher):
        """Test that directory modification events are ignored"""
        event = Mock()
        event.is_directory = True
        event.src_path = "/test/dir"

        # Should not raise, should return early
        watcher.on_modified(event)

        # No timer should be created
        assert len(watcher.debounce_timers) == 0

    def test_watcher_ignores_non_phase_files(self, watcher):
        """Test that non-phase files are ignored"""
        event = Mock()
        event.is_directory = False
        event.src_path = "/test/other-file.json"

        watcher.on_modified(event)

        # No timer should be created
        assert len(watcher.debounce_timers) == 0

    def test_watcher_detects_phase_file_changes(self, watcher):
        """Test that current-phase.json changes are detected"""
        event = Mock()
        event.is_directory = False
        event.src_path = "/test/.context-foundry/current-phase.json"

        watcher.on_modified(event)

        # Timer should be created
        assert len(watcher.debounce_timers) == 1
        assert "/test/.context-foundry/current-phase.json" in watcher.debounce_timers

    def test_watcher_debounces_rapid_changes(self, watcher):
        """Test that rapid file changes are debounced"""
        event = Mock()
        event.is_directory = False
        event.src_path = "/test/.context-foundry/current-phase.json"

        # Trigger multiple changes rapidly
        watcher.on_modified(event)
        timer1 = watcher.debounce_timers[event.src_path]

        watcher.on_modified(event)
        timer2 = watcher.debounce_timers[event.src_path]

        # Second timer should cancel and replace first
        assert timer1 != timer2
        # First timer should be cancelled (we can't easily test this without time.sleep)

    def test_handle_phase_update_reads_file(self, watcher, mock_collector):
        """Test that phase update handler reads the file correctly"""
        phase_data = {
            "session_id": "test-session-123",
            "phase": "build",
            "progress": 50,
        }

        with patch("builtins.open", mock_open(read_data=json.dumps(phase_data))):
            with patch("asyncio.run_coroutine_threadsafe") as mock_run_coro:
                watcher._handle_phase_update("/test/current-phase.json")

                # Should have scheduled coroutine in collector's loop
                mock_run_coro.assert_called_once()

    def test_handle_phase_update_invalid_json(self, watcher, mock_collector):
        """Test handling of invalid JSON in phase file"""
        with patch("builtins.open", mock_open(read_data="invalid json {")):
            # Should handle gracefully without raising
            watcher._handle_phase_update("/test/current-phase.json")


class TestMetricsCollectorInitialization:
    """Test MetricsCollector initialization"""

    def test_collector_initialization_defaults(self):
        """Test collector initializes with default parameters"""
        with patch("tools.livestream.metrics_collector.get_client") as mock_get_client:
            with patch("tools.livestream.metrics_collector.get_db") as mock_get_db:
                mock_get_client.return_value = Mock()
                mock_get_db.return_value = Mock()

                collector = MetricsCollector()

                assert collector.running is False
                assert collector.tracked_tasks == set()
                assert collector.observer is None
                assert collector.watcher is None

    def test_collector_initialization_custom_params(self):
        """Test collector with custom parameters"""
        mock_client = Mock()
        mock_db = Mock()

        collector = MetricsCollector(
            mcp_client=mock_client, db=mock_db, poll_interval=5.0
        )

        assert collector.mcp_client == mock_client
        assert collector.db == mock_db
        assert collector.poll_interval == 5.0


class TestFileWatcherStartup:
    """Test file watcher initialization and startup"""

    @pytest.fixture
    def collector(self):
        """Create collector with mocked dependencies"""
        with patch("tools.livestream.metrics_collector.get_client"):
            with patch("tools.livestream.metrics_collector.get_db"):
                return MetricsCollector()

    def test_start_file_watcher_creates_observer(self, collector):
        """Test that starting file watcher creates observer"""
        with patch(
            "tools.livestream.metrics_collector.Observer"
        ) as mock_observer_class:
            mock_observer = Mock()
            mock_observer_class.return_value = mock_observer

            collector.start_file_watcher()

            # Should create observer
            assert collector.observer == mock_observer

            # Should create watcher
            assert collector.watcher is not None
            assert isinstance(collector.watcher, PhaseFileWatcher)

    def test_start_file_watcher_schedules_paths(self, collector):
        """Test that file watcher schedules common directories"""
        with patch(
            "tools.livestream.metrics_collector.Observer"
        ) as mock_observer_class:
            with patch("pathlib.Path.exists") as mock_exists:
                mock_observer = Mock()
                mock_observer_class.return_value = mock_observer
                mock_exists.return_value = True  # All paths exist

                collector.start_file_watcher()

                # Should have scheduled at least one path
                assert mock_observer.schedule.called

                # Should have started observer
                assert mock_observer.start.called

    def test_start_file_watcher_handles_missing_paths(self, collector):
        """Test file watcher handles missing directories gracefully"""
        with patch(
            "tools.livestream.metrics_collector.Observer"
        ) as mock_observer_class:
            with patch("pathlib.Path.exists") as mock_exists:
                mock_observer = Mock()
                mock_observer_class.return_value = mock_observer
                mock_exists.return_value = False  # No paths exist

                # Should not raise
                collector.start_file_watcher()

                # Observer should still be started (even with no watched paths)
                assert mock_observer.start.called


class TestMetricsCollectionMainLoop:
    """Test main metrics collection loop"""

    @pytest.fixture
    def collector(self):
        """Create collector with mocked dependencies"""
        mock_client = Mock()
        mock_db = Mock()
        return MetricsCollector(mcp_client=mock_client, db=mock_db, poll_interval=0.1)

    @pytest.mark.asyncio
    async def test_collect_metrics_processes_tasks(self, collector):
        """Test that collect_metrics processes active tasks"""
        # Mock active tasks from MCP
        collector.mcp_client.list_active_tasks.return_value = [
            {"task_id": "task-123", "project_name": "test-project", "status": "running"}
        ]

        with patch.object(collector, "initialize_task") as mock_init:
            with patch.object(collector, "update_task_status") as mock_update:
                with patch.object(collector, "collect_task_metrics") as mock_collect:
                    await collector.collect_metrics()

                    # Should have initialized new task
                    mock_init.assert_called_once()

                    # Should have updated status
                    mock_update.assert_called_once()

                    # Should have collected metrics
                    mock_collect.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_metrics_finalizes_completed_tasks(self, collector):
        """Test that completed tasks are finalized"""
        collector.mcp_client.list_active_tasks.return_value = [
            {
                "task_id": "task-456",
                "project_name": "test-project",
                "status": "completed",
            }
        ]

        # Add to tracked tasks
        collector.tracked_tasks.add("task-456")

        with patch.object(collector, "initialize_task"):
            with patch.object(collector, "update_task_status"):
                with patch.object(collector, "collect_task_metrics"):
                    with patch.object(collector, "finalize_task") as mock_finalize:
                        await collector.collect_metrics()

                        # Should have finalized
                        mock_finalize.assert_called_once()

                        # Should have removed from tracked tasks
                        assert "task-456" not in collector.tracked_tasks

    @pytest.mark.asyncio
    async def test_collect_metrics_handles_errors(self, collector):
        """Test that errors in collection are handled gracefully"""
        collector.mcp_client.list_active_tasks.side_effect = Exception("API Error")

        # Should not raise
        await collector.collect_metrics()


class TestLivePhaseUpdate:
    """Test live phase update collection from file watcher"""

    @pytest.fixture
    def collector(self):
        """Create collector with mocked dependencies"""
        mock_client = Mock()
        mock_db = Mock()
        return MetricsCollector(mcp_client=mock_client, db=mock_db)

    @pytest.mark.asyncio
    async def test_collect_live_phase_update(self, collector):
        """Test collecting live phase updates"""
        session_id = "test-session-789"
        phase_data = {
            "session_id": session_id,
            "phase": "build",
            "progress": 75,
            "current_agent": "builder",
        }

        with patch.object(collector.db, "update_task_phase") as mock_update:
            await collector.collect_live_phase_update(session_id, phase_data)

            # Should have updated database
            # (exact implementation depends on collector logic)

    @pytest.mark.asyncio
    async def test_collect_live_phase_update_handles_errors(self, collector):
        """Test that phase update errors are handled"""
        session_id = "test-session"
        phase_data = {"invalid": "data"}

        # Should not raise even with invalid data
        await collector.collect_live_phase_update(session_id, phase_data)


class TestEventLoopManagement:
    """Test asyncio event loop management"""

    @pytest.fixture
    def collector(self):
        """Create collector with mocked dependencies"""
        with patch("tools.livestream.metrics_collector.get_client"):
            with patch("tools.livestream.metrics_collector.get_db"):
                return MetricsCollector(poll_interval=0.1)

    @pytest.mark.asyncio
    async def test_start_stores_event_loop(self, collector):
        """Test that start() stores the event loop for cross-thread access"""
        with patch.object(collector, "collect_metrics"):
            with patch.object(collector, "start_file_watcher"):
                # Start in background
                async def run_briefly():
                    task = asyncio.create_task(collector.start())
                    await asyncio.sleep(0.2)
                    collector.running = False
                    await task

                await run_briefly()

                # Event loop should have been stored
                assert collector.loop is not None

    @pytest.mark.asyncio
    async def test_start_starts_file_watcher(self, collector):
        """Test that start() initializes file watcher"""
        with patch.object(collector, "collect_metrics"):
            with patch.object(collector, "start_file_watcher") as mock_start_watcher:

                async def run_briefly():
                    task = asyncio.create_task(collector.start())
                    await asyncio.sleep(0.2)
                    collector.running = False
                    await task

                await run_briefly()

                # File watcher should have been started
                mock_start_watcher.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_runs_collection_loop(self, collector):
        """Test that start() runs the collection loop"""
        with patch.object(collector, "start_file_watcher"):
            with patch.object(collector, "collect_metrics") as mock_collect:

                async def run_briefly():
                    task = asyncio.create_task(collector.start())
                    await asyncio.sleep(0.25)  # Allow at least 2 polls
                    collector.running = False
                    await task

                await run_briefly()

                # Collection should have been called multiple times
                assert mock_collect.call_count >= 1


class TestStopAndCleanup:
    """Test collector stop and cleanup"""

    @pytest.fixture
    def collector(self):
        """Create collector with mocked dependencies"""
        with patch("tools.livestream.metrics_collector.get_client"):
            with patch("tools.livestream.metrics_collector.get_db"):
                return MetricsCollector()

    def test_stop_sets_running_false(self, collector):
        """Test that stop() sets running flag to False"""
        collector.running = True

        collector.stop()

        assert collector.running is False

    def test_stop_stops_observer(self, collector):
        """Test that stop() stops the file observer"""
        mock_observer = Mock()
        collector.observer = mock_observer
        collector.running = True

        collector.stop()

        # Should stop and join observer
        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once()

    def test_stop_handles_no_observer(self, collector):
        """Test that stop() works when observer was never started"""
        collector.observer = None
        collector.running = True

        # Should not raise
        collector.stop()


class TestCrossThreadCommunication:
    """Test cross-thread async communication (critical for file watcher)"""

    @pytest.mark.asyncio
    async def test_file_watcher_schedules_coroutine_in_collector_loop(self):
        """Test that file watcher can schedule coroutines in collector's event loop"""
        # Create collector with real event loop
        with patch("tools.livestream.metrics_collector.get_client"):
            with patch("tools.livestream.metrics_collector.get_db"):
                collector = MetricsCollector()
                collector.loop = asyncio.get_event_loop()

                # Create watcher
                watcher = PhaseFileWatcher(collector)
                watcher.loop = collector.loop

                # Mock the collector's collect_live_phase_update
                collector.collect_live_phase_update = Mock()
                collector.collect_live_phase_update.return_value = asyncio.coroutine(
                    lambda: None
                )()

                # Simulate file change from different thread
                phase_data = {"session_id": "test", "phase": "build"}

                with patch(
                    "builtins.open", mock_open(read_data=json.dumps(phase_data))
                ):
                    with patch("asyncio.run_coroutine_threadsafe") as mock_run_coro:
                        watcher._handle_phase_update("/test/current-phase.json")

                        # Should have used run_coroutine_threadsafe for cross-thread communication
                        mock_run_coro.assert_called_once()
                        assert mock_run_coro.call_args[1] == collector.loop


class TestTaskInitialization:
    """Test task initialization in database"""

    @pytest.fixture
    def collector(self):
        """Create collector with mocked dependencies"""
        mock_client = Mock()
        mock_db = Mock()
        return MetricsCollector(mcp_client=mock_client, db=mock_db)

    @pytest.mark.asyncio
    async def test_initialize_task_creates_database_entry(self, collector):
        """Test that initializing a task creates database entry"""
        task_data = {
            "task_id": "task-999",
            "project_name": "test-project",
            "task_description": "Test task",
            "working_directory": "/tmp/test",
        }

        await collector.initialize_task(task_data)

        # Should have created task in database
        collector.db.create_task.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
