"""
Event Bus for Context Foundry Daemon

Provides a thread-safe event system for real-time updates.
JobManager publishes events, SSE endpoints subscribe to receive them.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Set


logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events that can be published."""

    # Job lifecycle events
    JOB_CREATED = "job_created"
    JOB_STARTED = "job_started"
    JOB_UPDATED = "job_update"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_CANCELLED = "job_cancelled"

    # Phase events
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PHASE_FAILED = "phase_failed"
    PHASE_UPDATE = "phase_update"

    # Task events
    TASK_STARTED = "task_started"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"

    # Log events
    LOG = "log"

    # Metrics events
    METRICS = "metrics"

    # Connection events
    HEARTBEAT = "heartbeat"


@dataclass
class Event:
    """Represents a single event in the system."""

    type: EventType
    job_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        return {
            "type": self.type.value,
            "job_id": self.job_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }


# Type for event handlers
EventHandler = Callable[[Event], None]


class EventBus:
    """
    Thread-safe event bus for publishing and subscribing to events.

    Uses a queue-based approach for SSE streaming:
    - Publishers call publish() to add events
    - Subscribers call subscribe() to get a Queue that receives events
    - Each subscriber gets their own queue (fan-out pattern)
    """

    def __init__(self, max_queue_size: int = 1000):
        """
        Initialize the event bus.

        Args:
            max_queue_size: Maximum events to buffer per subscriber
        """
        self._lock = threading.RLock()
        self._subscribers: Dict[int, Queue] = {}
        self._subscriber_filters: Dict[int, Optional[Set[str]]] = {}
        self._next_id = 0
        self._max_queue_size = max_queue_size

        # Recent events buffer for new subscribers (last 50 events)
        self._recent_events: List[Event] = []
        self._max_recent = 50

        logger.info("EventBus initialized")

    def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.

        Args:
            event: The event to publish
        """
        with self._lock:
            # Add to recent events buffer
            self._recent_events.append(event)
            if len(self._recent_events) > self._max_recent:
                self._recent_events.pop(0)

            # Fan out to all subscriber queues
            for sub_id, queue in list(self._subscribers.items()):
                # Check if subscriber has a job filter
                job_filter = self._subscriber_filters.get(sub_id)
                if job_filter is not None and event.job_id not in job_filter:
                    continue

                try:
                    if queue.qsize() < self._max_queue_size:
                        queue.put_nowait(event)
                    else:
                        # Queue full, skip this event for this subscriber
                        logger.warning(
                            f"Event queue full for subscriber {sub_id}, dropping event"
                        )
                except Exception as e:
                    logger.error(f"Failed to publish to subscriber {sub_id}: {e}")

        logger.debug(f"Published event: {event.type.value} for job {event.job_id}")

    def subscribe(
        self,
        job_ids: Optional[Set[str]] = None,
        include_recent: bool = True,
    ) -> tuple[int, Queue]:
        """
        Subscribe to events.

        Args:
            job_ids: Optional set of job IDs to filter by (None = all jobs)
            include_recent: Whether to prepopulate queue with recent events

        Returns:
            Tuple of (subscriber_id, event_queue)
        """
        with self._lock:
            sub_id = self._next_id
            self._next_id += 1

            queue: Queue = Queue(maxsize=self._max_queue_size)
            self._subscribers[sub_id] = queue
            self._subscriber_filters[sub_id] = job_ids

            # Optionally include recent events
            if include_recent:
                for event in self._recent_events:
                    if job_ids is None or event.job_id in job_ids:
                        try:
                            queue.put_nowait(event)
                        except Exception:
                            break  # Queue full

            logger.debug(f"Subscriber {sub_id} registered (filter: {job_ids})")
            return sub_id, queue

    def unsubscribe(self, subscriber_id: int) -> None:
        """
        Unsubscribe from events.

        Args:
            subscriber_id: The subscriber ID returned from subscribe()
        """
        with self._lock:
            if subscriber_id in self._subscribers:
                del self._subscribers[subscriber_id]
                del self._subscriber_filters[subscriber_id]
                logger.debug(f"Subscriber {subscriber_id} unregistered")

    def get_subscriber_count(self) -> int:
        """Get the number of active subscribers."""
        with self._lock:
            return len(self._subscribers)

    def get_recent_events(self, limit: int = 50) -> List[Event]:
        """Get recent events from the buffer."""
        with self._lock:
            return list(self._recent_events[-limit:])


# Global event bus instance
_event_bus: Optional[EventBus] = None
_event_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Get or create the global event bus instance."""
    global _event_bus

    with _event_bus_lock:
        if _event_bus is None:
            _event_bus = EventBus()
        return _event_bus


def reset_event_bus() -> None:
    """Reset the global event bus (for testing)."""
    global _event_bus

    with _event_bus_lock:
        _event_bus = None


# Convenience functions for publishing common events


def emit_job_created(job_id: str, job_data: Dict[str, Any]) -> None:
    """Emit a job created event."""
    get_event_bus().publish(
        Event(
            type=EventType.JOB_CREATED,
            job_id=job_id,
            data=job_data,
        )
    )


def emit_job_started(job_id: str, job_data: Optional[Dict[str, Any]] = None) -> None:
    """Emit a job started event."""
    get_event_bus().publish(
        Event(
            type=EventType.JOB_STARTED,
            job_id=job_id,
            data=job_data or {},
        )
    )


def emit_job_updated(job_id: str, updates: Dict[str, Any]) -> None:
    """Emit a job update event with changed fields."""
    get_event_bus().publish(
        Event(
            type=EventType.JOB_UPDATED,
            job_id=job_id,
            data=updates,
        )
    )


def emit_job_completed(job_id: str, result: Optional[Dict[str, Any]] = None) -> None:
    """Emit a job completed event."""
    get_event_bus().publish(
        Event(
            type=EventType.JOB_COMPLETED,
            job_id=job_id,
            data={"result": result} if result else {},
        )
    )


def emit_job_failed(job_id: str, error: str) -> None:
    """Emit a job failed event."""
    get_event_bus().publish(
        Event(
            type=EventType.JOB_FAILED,
            job_id=job_id,
            data={"error": error},
        )
    )


def emit_phase_update(
    job_id: str,
    phase: str,
    status: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Emit a phase update event."""
    data = {"phase": phase, "status": status}
    if extra:
        data.update(extra)

    get_event_bus().publish(
        Event(
            type=EventType.PHASE_UPDATE,
            job_id=job_id,
            data=data,
        )
    )


def emit_log(job_id: str, level: str, message: str, source: str = "daemon") -> None:
    """Emit a log event."""
    get_event_bus().publish(
        Event(
            type=EventType.LOG,
            job_id=job_id,
            data={
                "level": level,
                "message": message,
                "source": source,
            },
        )
    )


def emit_heartbeat() -> None:
    """Emit a heartbeat event for connection keepalive."""
    get_event_bus().publish(
        Event(
            type=EventType.HEARTBEAT,
            data={"time": datetime.now().isoformat()},
        )
    )
