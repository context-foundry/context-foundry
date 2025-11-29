"""
Metrics abstraction for Context Foundry Daemon.

Provides a simple metrics interface with no-op defaults.
Can be extended to integrate with Prometheus, StatsD, or other backends.

Usage:
    from context_foundry.daemon.metrics import get_metrics

    metrics = get_metrics()
    metrics.inc_jobs_started()
    metrics.inc_jobs_succeeded()
    metrics.record_phase_duration("Builder", 45.2)
"""

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


# =============================================================================
# METRICS INTERFACE
# =============================================================================


class MetricsBackend(ABC):
    """Abstract base class for metrics backends."""

    @abstractmethod
    def increment(
        self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric."""
        pass

    @abstractmethod
    def gauge(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Set a gauge metric."""
        pass

    @abstractmethod
    def timing(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a timing metric in seconds."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        pass


# =============================================================================
# NO-OP BACKEND (Default)
# =============================================================================


class NoOpMetricsBackend(MetricsBackend):
    """No-op metrics backend that does nothing (default)."""

    def increment(
        self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ) -> None:
        pass

    def gauge(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        pass

    def timing(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        pass

    def get_stats(self) -> Dict[str, Any]:
        return {}


# =============================================================================
# IN-MEMORY BACKEND (For development/testing)
# =============================================================================


@dataclass
class InMemoryMetricsBackend(MetricsBackend):
    """In-memory metrics backend for development and testing."""

    counters: Dict[str, int] = field(default_factory=dict)
    gauges: Dict[str, float] = field(default_factory=dict)
    timings: Dict[str, list] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def increment(
        self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ) -> None:
        key = self._make_key(name, tags)
        with self._lock:
            self.counters[key] = self.counters.get(key, 0) + value

    def gauge(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        key = self._make_key(name, tags)
        with self._lock:
            self.gauges[key] = value

    def timing(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        key = self._make_key(name, tags)
        with self._lock:
            if key not in self.timings:
                self.timings[key] = []
            self.timings[key].append(value)
            # Keep only last 1000 timings per metric
            if len(self.timings[key]) > 1000:
                self.timings[key] = self.timings[key][-1000:]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            stats = {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "timings": {},
            }
            for key, values in self.timings.items():
                if values:
                    stats["timings"][key] = {
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                        "last": values[-1],
                    }
            return stats

    def _make_key(self, name: str, tags: Optional[Dict[str, str]] = None) -> str:
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}{{{tag_str}}}"

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self.counters.clear()
            self.gauges.clear()
            self.timings.clear()


# =============================================================================
# DAEMON METRICS FACADE
# =============================================================================


class DaemonMetrics:
    """
    High-level metrics facade for the daemon.

    Provides domain-specific methods for common metrics.
    """

    def __init__(self, backend: Optional[MetricsBackend] = None):
        self._backend = backend or NoOpMetricsBackend()
        self._start_time = datetime.now()

    @property
    def backend(self) -> MetricsBackend:
        return self._backend

    # =========================================================================
    # JOB METRICS
    # =========================================================================

    def inc_jobs_started(self) -> None:
        """Increment jobs started counter."""
        self._backend.increment("daemon.jobs.started")
        logger.debug("Metric: jobs_started incremented")

    def inc_jobs_succeeded(self) -> None:
        """Increment jobs succeeded counter."""
        self._backend.increment("daemon.jobs.succeeded")
        logger.debug("Metric: jobs_succeeded incremented")

    def inc_jobs_failed(self, reason: Optional[str] = None) -> None:
        """Increment jobs failed counter."""
        tags = {"reason": reason} if reason else None
        self._backend.increment("daemon.jobs.failed", tags=tags)
        logger.debug(f"Metric: jobs_failed incremented (reason={reason})")

    def inc_jobs_stalled(self) -> None:
        """Increment jobs stalled counter."""
        self._backend.increment("daemon.jobs.stalled")
        logger.debug("Metric: jobs_stalled incremented")

    def inc_jobs_timed_out(self) -> None:
        """Increment jobs timed out counter."""
        self._backend.increment("daemon.jobs.timed_out")
        logger.debug("Metric: jobs_timed_out incremented")

    def inc_jobs_cancelled(self) -> None:
        """Increment jobs cancelled counter."""
        self._backend.increment("daemon.jobs.cancelled")
        logger.debug("Metric: jobs_cancelled incremented")

    def set_jobs_active(self, count: int) -> None:
        """Set gauge for active jobs count."""
        self._backend.gauge("daemon.jobs.active", count)

    def set_jobs_queued(self, count: int) -> None:
        """Set gauge for queued jobs count."""
        self._backend.gauge("daemon.jobs.queued", count)

    def record_job_duration(self, duration_seconds: float) -> None:
        """Record job duration timing."""
        self._backend.timing("daemon.jobs.duration_seconds", duration_seconds)

    # =========================================================================
    # TASK/PHASE METRICS
    # =========================================================================

    def inc_tasks_started(self, phase: str) -> None:
        """Increment tasks started counter for a phase."""
        self._backend.increment("daemon.tasks.started", tags={"phase": phase})

    def inc_tasks_succeeded(self, phase: str) -> None:
        """Increment tasks succeeded counter for a phase."""
        self._backend.increment("daemon.tasks.succeeded", tags={"phase": phase})

    def inc_tasks_failed(self, phase: str, reason: Optional[str] = None) -> None:
        """Increment tasks failed counter for a phase."""
        tags = {"phase": phase}
        if reason:
            tags["reason"] = reason
        self._backend.increment("daemon.tasks.failed", tags=tags)

    def inc_tasks_timed_out(self, phase: str) -> None:
        """Increment tasks timed out counter for a phase."""
        self._backend.increment("daemon.tasks.timed_out", tags={"phase": phase})

    def record_phase_duration(self, phase: str, duration_seconds: float) -> None:
        """Record phase execution duration."""
        self._backend.timing(
            "daemon.phases.duration_seconds",
            duration_seconds,
            tags={"phase": phase},
        )

    def record_phase_tokens(self, phase: str, tokens: int) -> None:
        """Record tokens used by a phase."""
        self._backend.timing(
            "daemon.phases.tokens", float(tokens), tags={"phase": phase}
        )

    # =========================================================================
    # GATE METRICS
    # =========================================================================

    def inc_gates_passed(self, phase: str) -> None:
        """Increment gates passed counter."""
        self._backend.increment("daemon.gates.passed", tags={"phase": phase})

    def inc_gates_failed(self, phase: str) -> None:
        """Increment gates failed counter."""
        self._backend.increment("daemon.gates.failed", tags={"phase": phase})

    # =========================================================================
    # WATCHDOG METRICS
    # =========================================================================

    def inc_watchdog_iterations(self) -> None:
        """Increment watchdog loop iterations."""
        self._backend.increment("daemon.watchdog.iterations")

    def inc_watchdog_stale_tasks_detected(self) -> None:
        """Increment stale tasks detected by watchdog."""
        self._backend.increment("daemon.watchdog.stale_tasks_detected")

    def inc_watchdog_stale_jobs_detected(self) -> None:
        """Increment stale jobs detected by watchdog."""
        self._backend.increment("daemon.watchdog.stale_jobs_detected")

    def inc_watchdog_auto_completions(self) -> None:
        """Increment jobs auto-completed by watchdog."""
        self._backend.increment("daemon.watchdog.auto_completions")

    # =========================================================================
    # HEARTBEAT METRICS
    # =========================================================================

    def inc_heartbeats_received(self) -> None:
        """Increment heartbeats received."""
        self._backend.increment("daemon.heartbeats.received")

    def record_heartbeat_age(self, age_seconds: float) -> None:
        """Record heartbeat age at detection time."""
        self._backend.timing("daemon.heartbeats.age_seconds", age_seconds)

    # =========================================================================
    # SYSTEM METRICS
    # =========================================================================

    def set_daemon_uptime(self) -> None:
        """Update daemon uptime gauge."""
        uptime = (datetime.now() - self._start_time).total_seconds()
        self._backend.gauge("daemon.uptime_seconds", uptime)

    def get_stats(self) -> Dict[str, Any]:
        """Get all current metrics."""
        return self._backend.get_stats()


# =============================================================================
# GLOBAL METRICS INSTANCE
# =============================================================================

_metrics_instance: Optional[DaemonMetrics] = None
_metrics_lock = threading.Lock()


def init_metrics(
    backend: Optional[MetricsBackend] = None, enable: bool = True
) -> DaemonMetrics:
    """
    Initialize the global metrics instance.

    Args:
        backend: Metrics backend to use. If None, uses NoOp (disabled) or InMemory (enabled).
        enable: If True and no backend provided, uses InMemoryMetricsBackend.

    Returns:
        The initialized DaemonMetrics instance.
    """
    global _metrics_instance
    with _metrics_lock:
        if backend:
            _metrics_instance = DaemonMetrics(backend)
        elif enable:
            _metrics_instance = DaemonMetrics(InMemoryMetricsBackend())
        else:
            _metrics_instance = DaemonMetrics(NoOpMetricsBackend())
        return _metrics_instance


def get_metrics() -> DaemonMetrics:
    """
    Get the global metrics instance.

    If not initialized, creates a no-op instance.

    Returns:
        The DaemonMetrics instance.
    """
    global _metrics_instance
    if _metrics_instance is None:
        with _metrics_lock:
            if _metrics_instance is None:
                # Default to no-op to avoid overhead when metrics not explicitly enabled
                _metrics_instance = DaemonMetrics(NoOpMetricsBackend())
    return _metrics_instance


def reset_metrics() -> None:
    """Reset the global metrics instance (for testing)."""
    global _metrics_instance
    with _metrics_lock:
        _metrics_instance = None


# =============================================================================
# STRUCTURED LOG HELPERS
# =============================================================================


def make_structured_log(
    event: str,
    job_id: Optional[str] = None,
    task_id: Optional[str] = None,
    phase: Optional[str] = None,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    reason: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """
    Create a structured log dictionary.

    Args:
        event: Event name (e.g., "job_started", "task_failed")
        job_id: Job ID
        task_id: Task ID
        phase: Phase name
        old_status: Previous status
        new_status: New status
        reason: Reason for transition
        duration_seconds: Duration in seconds
        **extra: Additional fields

    Returns:
        Dictionary suitable for structured logging
    """
    log_dict = {
        "event": event,
        "timestamp": datetime.now().isoformat(),
    }

    if job_id:
        log_dict["job_id"] = job_id
    if task_id:
        log_dict["task_id"] = task_id
    if phase:
        log_dict["phase"] = phase
    if old_status:
        log_dict["old_status"] = old_status
    if new_status:
        log_dict["new_status"] = new_status
    if reason:
        log_dict["reason"] = reason
    if duration_seconds is not None:
        log_dict["duration_seconds"] = duration_seconds

    log_dict.update(extra)

    return log_dict


def log_structured(
    logger_instance: logging.Logger,
    level: int,
    message: str,
    **kwargs: Any,
) -> None:
    """
    Log a structured message.

    Args:
        logger_instance: Logger to use
        level: Log level
        message: Human-readable message
        **kwargs: Structured data fields
    """
    structured = make_structured_log(**kwargs)
    # Log as JSON for structured log aggregators
    import json

    logger_instance.log(level, f"{message} | {json.dumps(structured)}")
