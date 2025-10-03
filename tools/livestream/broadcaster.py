#!/usr/bin/env python3
"""
Event Broadcaster for Context Foundry
Publishes real-time updates during execution
"""

import json
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Callable, List
from collections import defaultdict


class EventBroadcaster:
    """
    Broadcasts events to livestream server and records for replay.

    Usage:
        broadcaster = EventBroadcaster(session_id="my_session")
        broadcaster.emit("iteration_start", {"iteration": 5})
        broadcaster.emit("task_complete", {"task": "Setup", "context": 25})
    """

    def __init__(
        self,
        session_id: str,
        server_url: str = "http://localhost:8080",
        enable_recording: bool = True,
    ):
        self.session_id = session_id
        self.server_url = server_url
        self.enable_recording = enable_recording

        # Event recording
        self.events_dir = Path(f"logs/events/{session_id}")
        if enable_recording:
            self.events_dir.mkdir(parents=True, exist_ok=True)
            self.events_file = self.events_dir / "events.jsonl"

        # Subscribers (for in-process events)
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)

        # State tracking
        self.event_count = 0

    def emit(self, event_type: str, data: Optional[Dict] = None):
        """
        Emit an event.

        Args:
            event_type: Type of event (e.g., "iteration_start", "task_complete")
            data: Event data dictionary
        """
        self.event_count += 1

        event = {
            "type": event_type,
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "sequence": self.event_count,
            "data": data or {},
        }

        # Record event
        if self.enable_recording:
            self._record_event(event)

        # Broadcast to livestream server
        self._broadcast_to_server(event)

        # Notify local subscribers
        self._notify_subscribers(event_type, event)

    def _record_event(self, event: Dict):
        """Record event to JSONL file for replay."""
        try:
            with open(self.events_file, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            print(f"⚠️  Failed to record event: {e}")

    def _broadcast_to_server(self, event: Dict):
        """Broadcast event to livestream server via HTTP."""
        try:
            url = f"{self.server_url}/api/broadcast/{self.session_id}"
            requests.post(url, json=event, timeout=1)
        except requests.exceptions.ConnectionError:
            # Server not running - that's okay
            pass
        except Exception as e:
            # Don't let broadcast failures break execution
            pass

    def _notify_subscribers(self, event_type: str, event: Dict):
        """Notify in-process subscribers."""
        for callback in self.subscribers.get(event_type, []):
            try:
                callback(event)
            except Exception as e:
                print(f"⚠️  Subscriber error: {e}")

    def subscribe(self, event_type: str, callback: Callable):
        """
        Subscribe to events.

        Args:
            event_type: Event type to listen for
            callback: Function to call when event occurs
        """
        self.subscribers[event_type].append(callback)

    def load_events(self) -> List[Dict]:
        """Load recorded events for replay."""
        if not self.events_file.exists():
            return []

        events = []
        with open(self.events_file) as f:
            for line in f:
                try:
                    events.append(json.loads(line))
                except:
                    pass

        return events

    # Convenience methods for common events

    def phase_change(self, phase: str, context_percent: int = 0):
        """Emit phase change event."""
        self.emit(
            "phase_change",
            {"phase": phase, "context_percent": context_percent}
        )

    def iteration_start(self, iteration: int):
        """Emit iteration start event."""
        self.emit("iteration_start", {"iteration": iteration})

    def iteration_complete(self, iteration: int, context_percent: int):
        """Emit iteration complete event."""
        self.emit(
            "iteration_complete",
            {"iteration": iteration, "context_percent": context_percent},
        )

    def task_complete(self, task_name: str, context_percent: int):
        """Emit task complete event."""
        self.emit(
            "task_complete",
            {"task": task_name, "context_percent": context_percent}
        )

    def context_update(self, percent: int, tokens_used: int):
        """Emit context usage update."""
        self.emit(
            "context_update",
            {"percent": percent, "tokens_used": tokens_used}
        )

    def log_line(self, line: str, level: str = "info"):
        """Emit log line."""
        self.emit("log_line", {"line": line, "level": level})

    def error(self, message: str, details: Optional[Dict] = None):
        """Emit error event."""
        self.emit("error", {"message": message, "details": details or {}})

    def completion(self, success: bool, summary: Optional[Dict] = None):
        """Emit completion event."""
        self.emit(
            "completion",
            {"success": success, "summary": summary or {}}
        )


# Global broadcaster instance
_broadcaster: Optional[EventBroadcaster] = None


def get_broadcaster(session_id: Optional[str] = None) -> EventBroadcaster:
    """
    Get global broadcaster instance.

    Args:
        session_id: Session ID (required on first call)

    Returns:
        EventBroadcaster instance
    """
    global _broadcaster

    if _broadcaster is None:
        if session_id is None:
            raise ValueError("session_id required for first call to get_broadcaster()")
        _broadcaster = EventBroadcaster(session_id)

    return _broadcaster


def init_broadcaster(session_id: str, server_url: str = "http://localhost:8080") -> EventBroadcaster:
    """
    Initialize global broadcaster.

    Args:
        session_id: Session ID
        server_url: Livestream server URL

    Returns:
        EventBroadcaster instance
    """
    global _broadcaster
    _broadcaster = EventBroadcaster(session_id, server_url)
    return _broadcaster


# Example usage and testing
if __name__ == "__main__":
    import time

    print("🎥 Testing Event Broadcaster")
    print("=" * 60)

    # Create broadcaster
    broadcaster = EventBroadcaster(
        session_id="test_session",
        server_url="http://localhost:8080",
        enable_recording=True,
    )

    print(f"📡 Broadcasting to: http://localhost:8080")
    print(f"📁 Recording to: {broadcaster.events_file}")
    print()

    # Subscribe to events
    def on_task_complete(event):
        print(f"  ✓ Callback received: {event['data']['task']}")

    broadcaster.subscribe("task_complete", on_task_complete)

    # Simulate workflow
    print("🔍 SCOUT PHASE")
    broadcaster.phase_change("scout", context_percent=0)
    time.sleep(1)

    broadcaster.iteration_start(1)
    time.sleep(0.5)
    broadcaster.log_line("Researching architecture...")
    time.sleep(0.5)
    broadcaster.iteration_complete(1, context_percent=25)
    time.sleep(1)

    print("\n📐 ARCHITECT PHASE")
    broadcaster.phase_change("architect", context_percent=0)
    time.sleep(1)

    broadcaster.iteration_start(2)
    broadcaster.log_line("Creating specifications...")
    time.sleep(0.5)
    broadcaster.log_line("Generating task breakdown...")
    time.sleep(0.5)
    broadcaster.iteration_complete(2, context_percent=30)
    time.sleep(1)

    print("\n🔨 BUILDER PHASE")
    broadcaster.phase_change("builder", context_percent=0)
    time.sleep(1)

    tasks = ["Setup project", "Create models", "Add tests"]
    for i, task in enumerate(tasks, 1):
        print(f"  Task {i}: {task}")
        broadcaster.iteration_start(i + 2)
        broadcaster.log_line(f"Implementing {task}...")
        time.sleep(0.5)
        broadcaster.task_complete(task, context_percent=20 + i * 5)
        time.sleep(1)

    print("\n✅ COMPLETE")
    broadcaster.phase_change("complete", context_percent=0)
    broadcaster.completion(
        success=True,
        summary={"tasks": len(tasks), "iterations": len(tasks) + 2}
    )

    print(f"\n📊 Total events emitted: {broadcaster.event_count}")

    # Load and display events
    events = broadcaster.load_events()
    print(f"📼 Recorded events: {len(events)}")
    print("\nEvent summary:")
    for event in events:
        print(f"  [{event['sequence']}] {event['type']}")

    print("\n✅ Test complete!")
    print(f"Check events file: {broadcaster.events_file}")
