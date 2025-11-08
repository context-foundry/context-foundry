#!/usr/bin/env python3
"""
Tests for tools/evolution/resource_manager.py

These tests ensure the ResourceManager correctly monitors system resources
and enforces limits for CPU, memory, and active hours.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from tools.evolution.resource_manager import ResourceManager


class TestResourceManagerInit:
    """Tests for ResourceManager initialization"""

    def test_default_initialization(self):
        """Test initialization with default values"""
        manager = ResourceManager()
        assert manager.max_cpu_percent == 80
        assert manager.max_memory_gb == 16
        assert manager.active_hours == [6, 22]

    def test_custom_config(self):
        """Test initialization with custom config"""
        config = {
            'max_cpu_percent': 60,
            'max_memory_gb': 8,
            'active_hours': [8, 18]
        }
        manager = ResourceManager(config)
        assert manager.max_cpu_percent == 60
        assert manager.max_memory_gb == 8
        assert manager.active_hours == [8, 18]

    def test_partial_config(self):
        """Test initialization with partial config"""
        config = {'max_cpu_percent': 70}
        manager = ResourceManager(config)
        assert manager.max_cpu_percent == 70
        assert manager.max_memory_gb == 16  # Default
        assert manager.active_hours == [6, 22]  # Default

    def test_empty_config(self):
        """Test initialization with empty config"""
        manager = ResourceManager({})
        assert manager.max_cpu_percent == 80
        assert manager.max_memory_gb == 16
        assert manager.active_hours == [6, 22]


class TestCPUChecks:
    """Tests for CPU monitoring"""

    @patch('tools.evolution.resource_manager.psutil.cpu_percent')
    def test_cpu_within_limits(self, mock_cpu):
        """Test CPU usage within limits"""
        mock_cpu.return_value = 50.0
        manager = ResourceManager({'max_cpu_percent': 80})

        within_limits, usage = manager.check_cpu()
        assert within_limits is True
        assert usage == 50.0
        mock_cpu.assert_called_once_with(interval=1)

    @patch('tools.evolution.resource_manager.psutil.cpu_percent')
    def test_cpu_exceeds_limits(self, mock_cpu):
        """Test CPU usage exceeding limits"""
        mock_cpu.return_value = 85.0
        manager = ResourceManager({'max_cpu_percent': 80})

        within_limits, usage = manager.check_cpu()
        assert within_limits is False
        assert usage == 85.0

    @patch('tools.evolution.resource_manager.psutil.cpu_percent')
    def test_cpu_at_limit_boundary(self, mock_cpu):
        """Test CPU usage exactly at limit"""
        mock_cpu.return_value = 80.0
        manager = ResourceManager({'max_cpu_percent': 80})

        within_limits, usage = manager.check_cpu()
        assert within_limits is False  # Not strictly less than
        assert usage == 80.0


class TestMemoryChecks:
    """Tests for memory monitoring"""

    @patch('tools.evolution.resource_manager.psutil.virtual_memory')
    def test_memory_within_limits(self, mock_memory):
        """Test memory usage within limits"""
        mock_mem = Mock()
        mock_mem.used = 8 * (1024**3)  # 8 GB
        mock_memory.return_value = mock_mem

        manager = ResourceManager({'max_memory_gb': 16})
        within_limits, usage = manager.check_memory()

        assert within_limits is True
        assert usage == 8.0

    @patch('tools.evolution.resource_manager.psutil.virtual_memory')
    def test_memory_exceeds_limits(self, mock_memory):
        """Test memory usage exceeding limits"""
        mock_mem = Mock()
        mock_mem.used = 20 * (1024**3)  # 20 GB
        mock_memory.return_value = mock_mem

        manager = ResourceManager({'max_memory_gb': 16})
        within_limits, usage = manager.check_memory()

        assert within_limits is False
        assert usage == 20.0

    @patch('tools.evolution.resource_manager.psutil.virtual_memory')
    def test_memory_at_limit_boundary(self, mock_memory):
        """Test memory usage exactly at limit"""
        mock_mem = Mock()
        mock_mem.used = 16 * (1024**3)  # 16 GB
        mock_memory.return_value = mock_mem

        manager = ResourceManager({'max_memory_gb': 16})
        within_limits, usage = manager.check_memory()

        assert within_limits is False  # Not strictly less than
        assert usage == 16.0


class TestActiveHours:
    """Tests for active hours checking"""

    @patch('tools.evolution.resource_manager.datetime')
    def test_within_active_hours(self, mock_datetime):
        """Test time within active hours"""
        mock_now = Mock()
        mock_now.hour = 10
        mock_datetime.now.return_value = mock_now

        manager = ResourceManager({'active_hours': [6, 22]})
        is_active, current_hour = manager.is_active_hour()

        assert is_active is True
        assert current_hour == 10

    @patch('tools.evolution.resource_manager.datetime')
    def test_before_active_hours(self, mock_datetime):
        """Test time before active hours"""
        mock_now = Mock()
        mock_now.hour = 4
        mock_datetime.now.return_value = mock_now

        manager = ResourceManager({'active_hours': [6, 22]})
        is_active, current_hour = manager.is_active_hour()

        assert is_active is False
        assert current_hour == 4

    @patch('tools.evolution.resource_manager.datetime')
    def test_after_active_hours(self, mock_datetime):
        """Test time after active hours"""
        mock_now = Mock()
        mock_now.hour = 23
        mock_datetime.now.return_value = mock_now

        manager = ResourceManager({'active_hours': [6, 22]})
        is_active, current_hour = manager.is_active_hour()

        assert is_active is False
        assert current_hour == 23

    @patch('tools.evolution.resource_manager.datetime')
    def test_at_active_hour_start_boundary(self, mock_datetime):
        """Test time at start boundary"""
        mock_now = Mock()
        mock_now.hour = 6
        mock_datetime.now.return_value = mock_now

        manager = ResourceManager({'active_hours': [6, 22]})
        is_active, current_hour = manager.is_active_hour()

        assert is_active is True
        assert current_hour == 6

    @patch('tools.evolution.resource_manager.datetime')
    def test_at_active_hour_end_boundary(self, mock_datetime):
        """Test time at end boundary"""
        mock_now = Mock()
        mock_now.hour = 22
        mock_datetime.now.return_value = mock_now

        manager = ResourceManager({'active_hours': [6, 22]})
        is_active, current_hour = manager.is_active_hour()

        assert is_active is False  # Exclusive end
        assert current_hour == 22


class TestCanAcceptTask:
    """Tests for combined resource checking"""

    @patch('tools.evolution.resource_manager.psutil.cpu_percent')
    @patch('tools.evolution.resource_manager.psutil.virtual_memory')
    @patch('tools.evolution.resource_manager.datetime')
    def test_all_resources_ok(self, mock_datetime, mock_memory, mock_cpu):
        """Test when all resources are within limits"""
        mock_cpu.return_value = 50.0
        mock_mem = Mock()
        mock_mem.used = 8 * (1024**3)
        mock_memory.return_value = mock_mem
        mock_now = Mock()
        mock_now.hour = 10
        mock_datetime.now.return_value = mock_now

        manager = ResourceManager({
            'max_cpu_percent': 80,
            'max_memory_gb': 16,
            'active_hours': [6, 22]
        })

        can_accept, status = manager.can_accept_task()

        assert can_accept is True
        assert status['can_accept'] is True
        assert status['cpu_ok'] is True
        assert status['cpu_percent'] == 50.0
        assert status['memory_ok'] is True
        assert status['memory_gb'] == 8.0
        assert status['active_hour_ok'] is True
        assert status['current_hour'] == 10

    @patch('tools.evolution.resource_manager.psutil.cpu_percent')
    @patch('tools.evolution.resource_manager.psutil.virtual_memory')
    @patch('tools.evolution.resource_manager.datetime')
    def test_cpu_exceeded(self, mock_datetime, mock_memory, mock_cpu):
        """Test when CPU exceeds limit"""
        mock_cpu.return_value = 90.0
        mock_mem = Mock()
        mock_mem.used = 8 * (1024**3)
        mock_memory.return_value = mock_mem
        mock_now = Mock()
        mock_now.hour = 10
        mock_datetime.now.return_value = mock_now

        manager = ResourceManager()
        can_accept, status = manager.can_accept_task()

        assert can_accept is False
        assert status['cpu_ok'] is False

    @patch('tools.evolution.resource_manager.psutil.cpu_percent')
    @patch('tools.evolution.resource_manager.psutil.virtual_memory')
    @patch('tools.evolution.resource_manager.datetime')
    def test_memory_exceeded(self, mock_datetime, mock_memory, mock_cpu):
        """Test when memory exceeds limit"""
        mock_cpu.return_value = 50.0
        mock_mem = Mock()
        mock_mem.used = 20 * (1024**3)
        mock_memory.return_value = mock_mem
        mock_now = Mock()
        mock_now.hour = 10
        mock_datetime.now.return_value = mock_now

        manager = ResourceManager()
        can_accept, status = manager.can_accept_task()

        assert can_accept is False
        assert status['memory_ok'] is False

    @patch('tools.evolution.resource_manager.psutil.cpu_percent')
    @patch('tools.evolution.resource_manager.psutil.virtual_memory')
    @patch('tools.evolution.resource_manager.datetime')
    def test_outside_active_hours(self, mock_datetime, mock_memory, mock_cpu):
        """Test when outside active hours"""
        mock_cpu.return_value = 50.0
        mock_mem = Mock()
        mock_mem.used = 8 * (1024**3)
        mock_memory.return_value = mock_mem
        mock_now = Mock()
        mock_now.hour = 2
        mock_datetime.now.return_value = mock_now

        manager = ResourceManager()
        can_accept, status = manager.can_accept_task()

        assert can_accept is False
        assert status['active_hour_ok'] is False


class TestGetResourceUsage:
    """Tests for getting current resource usage"""

    @patch('tools.evolution.resource_manager.psutil.cpu_percent')
    @patch('tools.evolution.resource_manager.psutil.virtual_memory')
    @patch('tools.evolution.resource_manager.psutil.disk_usage')
    def test_get_resource_usage(self, mock_disk, mock_memory, mock_cpu):
        """Test getting full resource usage"""
        mock_cpu.return_value = 45.5

        mock_mem = Mock()
        mock_mem.percent = 60.0
        mock_mem.used = 12 * (1024**3)
        mock_memory.return_value = mock_mem

        mock_disk_info = Mock()
        mock_disk_info.percent = 75.0
        mock_disk_info.used = 500 * (1024**3)
        mock_disk.return_value = mock_disk_info

        manager = ResourceManager()
        usage = manager.get_resource_usage()

        assert usage['cpu_percent'] == 45.5
        assert usage['memory_percent'] == 60.0
        assert usage['memory_gb'] == 12.0
        assert usage['disk_percent'] == 75.0
        assert usage['disk_gb'] == 500.0
        mock_disk.assert_called_once_with('/')
