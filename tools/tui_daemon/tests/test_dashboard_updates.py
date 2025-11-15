"""
Tests for dashboard auto-refresh functionality
"""

import pytest
from unittest.mock import Mock

from tools.tui_daemon.manager import TUIManager
from tools.tui_daemon.widgets.job_table import JobTable


class TestDashboardUpdates:
    """Tests for dashboard data updates"""

    @pytest.fixture
    def manager(self, mock_daemon_client):
        """Create TUIManager with mocked client"""
        manager = TUIManager()
        manager.daemon_client = mock_daemon_client
        manager._connected = True
        return manager

    def test_get_current_jobs(self, manager):
        """Test retrieving current jobs"""
        jobs = manager.get_current_jobs(limit=10)

        assert len(jobs) == 3
        assert jobs[0].status == "succeeded"
        assert jobs[1].status == "running"

    def test_get_job_by_id(self, manager):
        """Test retrieving specific job"""
        job_id = "a3f2b1c4-0000-0000-0000-000000000001"
        job = manager.get_job(job_id)

        assert job is not None
        assert job.job_id == job_id

    @pytest.mark.asyncio
    async def test_job_table_update(self, mock_daemon_client):
        """Test updating job table with new data"""
        from textual.app import App

        jobs = mock_daemon_client.list_jobs()

        class TestApp(App):
            def compose(self):
                yield JobTable()

        app = TestApp()
        async with app.run_test() as pilot:
            table = app.query_one(JobTable)
            table.update_jobs(jobs)

            # Job table should have rows for each job
            assert len(table.rows) == 3

    def test_refresh_callbacks(self, manager):
        """Test refresh callback registration and triggering"""
        callback = Mock()

        manager.register_refresh_callback(callback)
        manager.trigger_refresh()

        callback.assert_called_once()

    def test_multiple_refresh_callbacks(self, manager):
        """Test multiple refresh callbacks"""
        callback1 = Mock()
        callback2 = Mock()

        manager.register_refresh_callback(callback1)
        manager.register_refresh_callback(callback2)
        manager.trigger_refresh()

        callback1.assert_called_once()
        callback2.assert_called_once()

    def test_auto_refresh_toggle(self, manager):
        """Test toggling auto-refresh"""
        assert manager.auto_refresh_enabled is True

        manager.toggle_auto_refresh()
        assert manager.auto_refresh_enabled is False

        manager.toggle_auto_refresh()
        assert manager.auto_refresh_enabled is True
