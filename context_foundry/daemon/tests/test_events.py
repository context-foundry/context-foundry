"""Tests for the event bus module."""

import threading
from queue import Empty


from context_foundry.daemon.events import (
    EventBus,
    Event,
    EventType,
    get_event_bus,
    reset_event_bus,
    emit_job_created,
    emit_job_started,
    emit_job_completed,
    emit_job_updated,
    emit_phase_update,
    emit_heartbeat,
)


class TestEventBus:
    """Tests for EventBus class."""

    def test_publish_and_subscribe(self):
        """Test basic publish/subscribe flow."""
        bus = EventBus()

        # Subscribe
        sub_id, queue = bus.subscribe()
        assert bus.get_subscriber_count() == 1

        # Publish event
        event = Event(
            type=EventType.JOB_CREATED,
            job_id="test-123",
            data={"status": "QUEUED"},
        )
        bus.publish(event)

        # Receive event
        received = queue.get(timeout=1.0)
        assert received.type == EventType.JOB_CREATED
        assert received.job_id == "test-123"
        assert received.data["status"] == "QUEUED"

        # Unsubscribe
        bus.unsubscribe(sub_id)
        assert bus.get_subscriber_count() == 0

    def test_multiple_subscribers(self):
        """Test that events are fanned out to all subscribers."""
        bus = EventBus()

        # Subscribe two clients
        sub_id1, queue1 = bus.subscribe()
        sub_id2, queue2 = bus.subscribe()

        # Publish event
        event = Event(type=EventType.HEARTBEAT)
        bus.publish(event)

        # Both should receive
        received1 = queue1.get(timeout=1.0)
        received2 = queue2.get(timeout=1.0)
        assert received1.type == EventType.HEARTBEAT
        assert received2.type == EventType.HEARTBEAT

        bus.unsubscribe(sub_id1)
        bus.unsubscribe(sub_id2)

    def test_job_filter(self):
        """Test that job filters work correctly."""
        bus = EventBus()

        # Subscribe to specific jobs only
        sub_id, queue = bus.subscribe(job_ids={"job-1", "job-2"})

        # Publish events for different jobs
        bus.publish(Event(type=EventType.JOB_UPDATED, job_id="job-1"))
        bus.publish(
            Event(type=EventType.JOB_UPDATED, job_id="job-3")
        )  # Should be filtered
        bus.publish(Event(type=EventType.JOB_UPDATED, job_id="job-2"))

        # Should only receive 2 events
        received = []
        for _ in range(3):
            try:
                received.append(queue.get(timeout=0.1))
            except Empty:
                break

        assert len(received) == 2
        assert received[0].job_id == "job-1"
        assert received[1].job_id == "job-2"

        bus.unsubscribe(sub_id)

    def test_recent_events_buffer(self):
        """Test that recent events are buffered."""
        bus = EventBus()

        # Publish some events before subscribing
        for i in range(5):
            bus.publish(Event(type=EventType.JOB_CREATED, job_id=f"job-{i}"))

        # Check recent events
        recent = bus.get_recent_events()
        assert len(recent) == 5

        # New subscriber with include_recent=True should get them
        sub_id, queue = bus.subscribe(include_recent=True)
        assert queue.qsize() == 5

        bus.unsubscribe(sub_id)

    def test_to_dict(self):
        """Test Event.to_dict serialization."""
        event = Event(
            type=EventType.JOB_FAILED,
            job_id="job-123",
            data={"error": "Something went wrong"},
        )

        d = event.to_dict()
        assert d["type"] == "job_failed"
        assert d["job_id"] == "job-123"
        assert d["data"]["error"] == "Something went wrong"
        assert "timestamp" in d


class TestConvenienceFunctions:
    """Tests for convenience emit functions."""

    def setup_method(self):
        """Reset event bus before each test."""
        reset_event_bus()

    def teardown_method(self):
        """Reset event bus after each test."""
        reset_event_bus()

    def test_emit_job_created(self):
        """Test emit_job_created convenience function."""
        bus = get_event_bus()
        sub_id, queue = bus.subscribe()

        emit_job_created("job-123", {"task": "Build something"})

        event = queue.get(timeout=1.0)
        assert event.type == EventType.JOB_CREATED
        assert event.job_id == "job-123"
        assert event.data["task"] == "Build something"

        bus.unsubscribe(sub_id)

    def test_emit_job_lifecycle(self):
        """Test full job lifecycle events."""
        bus = get_event_bus()
        sub_id, queue = bus.subscribe()

        # Emit lifecycle events
        emit_job_created("job-1", {"status": "QUEUED"})
        emit_job_started("job-1", {"started_at": "2024-01-01T00:00:00"})
        emit_job_updated("job-1", {"current_phase": "Scout"})
        emit_job_completed("job-1", {"output": "success"})

        # Verify all received
        events = []
        for _ in range(4):
            events.append(queue.get(timeout=1.0))

        assert events[0].type == EventType.JOB_CREATED
        assert events[1].type == EventType.JOB_STARTED
        assert events[2].type == EventType.JOB_UPDATED
        assert events[3].type == EventType.JOB_COMPLETED

        bus.unsubscribe(sub_id)

    def test_emit_phase_update(self):
        """Test emit_phase_update."""
        bus = get_event_bus()
        sub_id, queue = bus.subscribe()

        emit_phase_update("job-1", "Scout", "RUNNING")

        event = queue.get(timeout=1.0)
        assert event.type == EventType.PHASE_UPDATE
        assert event.data["phase"] == "Scout"
        assert event.data["status"] == "RUNNING"

        bus.unsubscribe(sub_id)

    def test_emit_heartbeat(self):
        """Test emit_heartbeat."""
        bus = get_event_bus()
        sub_id, queue = bus.subscribe()

        emit_heartbeat()

        event = queue.get(timeout=1.0)
        assert event.type == EventType.HEARTBEAT
        assert event.job_id is None

        bus.unsubscribe(sub_id)


class TestThreadSafety:
    """Tests for thread safety of event bus."""

    def test_concurrent_publish_subscribe(self):
        """Test that publish/subscribe works correctly under concurrent load."""
        bus = EventBus()
        received_events = []
        lock = threading.Lock()

        # Subscribe
        sub_id, queue = bus.subscribe()

        # Consumer thread
        def consumer():
            while True:
                try:
                    event = queue.get(timeout=0.5)
                    with lock:
                        received_events.append(event)
                except Empty:
                    break

        # Publisher threads
        def publisher(prefix: str, count: int):
            for i in range(count):
                bus.publish(
                    Event(
                        type=EventType.JOB_UPDATED,
                        job_id=f"{prefix}-{i}",
                    )
                )

        # Start threads
        consumer_thread = threading.Thread(target=consumer)
        pub1 = threading.Thread(target=publisher, args=("A", 10))
        pub2 = threading.Thread(target=publisher, args=("B", 10))

        consumer_thread.start()
        pub1.start()
        pub2.start()

        pub1.join()
        pub2.join()
        consumer_thread.join()

        # Should have received all 20 events
        assert len(received_events) == 20

        bus.unsubscribe(sub_id)
