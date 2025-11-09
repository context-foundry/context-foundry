#!/usr/bin/env python3
"""
Resource Manager for CFES
Monitor system resources and enforce limits
"""

import psutil
from datetime import datetime
from typing import Dict, Tuple


class ResourceManager:
    """Monitor and enforce resource limits"""

    def __init__(self, config: Dict = None):
        """
        Initialize resource manager

        Args:
            config: Configuration dict with max_cpu_percent, max_memory_gb, active_hours
        """
        config = config or {}
        self.max_cpu_percent = config.get("max_cpu_percent", 80)
        self.max_memory_gb = config.get("max_memory_gb", 16)
        self.active_hours = config.get("active_hours", [6, 22])  # [start, end]

    def check_cpu(self) -> Tuple[bool, float]:
        """
        Check if CPU usage is within limits

        Returns:
            (within_limits, current_usage)
        """
        cpu = psutil.cpu_percent(interval=1)
        return cpu < self.max_cpu_percent, cpu

    def check_memory(self) -> Tuple[bool, float]:
        """
        Check if memory usage is within limits

        Returns:
            (within_limits, memory_gb_used)
        """
        memory = psutil.virtual_memory()
        memory_gb = memory.used / (1024**3)
        return memory_gb < self.max_memory_gb, memory_gb

    def is_active_hour(self) -> Tuple[bool, int]:
        """
        Check if current time is within active hours

        Returns:
            (is_active, current_hour)
        """
        current_hour = datetime.now().hour
        start, end = self.active_hours
        return start <= current_hour < end, current_hour

    def can_accept_task(self) -> Tuple[bool, Dict[str, any]]:
        """
        Check all resource constraints

        Returns:
            (can_accept, resource_status)
        """
        cpu_ok, cpu_usage = self.check_cpu()
        memory_ok, memory_usage = self.check_memory()
        active_ok, current_hour = self.is_active_hour()

        can_accept = cpu_ok and memory_ok and active_ok

        status = {
            "can_accept": can_accept,
            "cpu_ok": cpu_ok,
            "cpu_percent": cpu_usage,
            "memory_ok": memory_ok,
            "memory_gb": memory_usage,
            "active_hour_ok": active_ok,
            "current_hour": current_hour,
        }

        return can_accept, status

    def get_resource_usage(self) -> Dict[str, float]:
        """Get current resource usage"""
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return {
            "cpu_percent": cpu,
            "memory_percent": memory.percent,
            "memory_gb": memory.used / (1024**3),
            "disk_percent": disk.percent,
            "disk_gb": disk.used / (1024**3),
        }
