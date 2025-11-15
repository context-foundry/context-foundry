"""
SSE Pub/Sub broadcaster for real-time event distribution.
"""

import asyncio
import logging
from typing import AsyncGenerator, Dict, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class Broadcaster:
    """
    Manages Server-Sent Events subscriptions and broadcasts.

    Supports multiple channels (e.g., "job:123", "global") with
    multiple subscribers per channel.
    """

    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, channel: str) -> AsyncGenerator[dict, None]:
        """
        Subscribe to a channel and receive events.

        Args:
            channel: Channel name (e.g., "job:550e8400-e29b-41d4-a716-446655440000")

        Yields:
            Event dictionaries
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        async with self._lock:
            self._subscribers[channel].add(queue)
            logger.info(
                f"New subscriber to channel: {channel} (total: {len(self._subscribers[channel])})"
            )

        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            async with self._lock:
                self._subscribers[channel].discard(queue)
                if not self._subscribers[channel]:
                    del self._subscribers[channel]
                logger.info(f"Subscriber removed from channel: {channel}")

    async def publish(self, channel: str, event: dict):
        """
        Publish an event to all subscribers of a channel.

        Args:
            channel: Channel name
            event: Event dictionary (must include 'type' and 'data' keys)
        """
        async with self._lock:
            subscribers = self._subscribers.get(channel, set()).copy()

        if not subscribers:
            logger.debug(f"No subscribers for channel: {channel}")
            return

        logger.debug(
            f"Publishing to {len(subscribers)} subscribers on channel: {channel}"
        )

        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"Subscriber queue full for channel: {channel}")

    def get_subscriber_count(self, channel: str) -> int:
        """Get number of active subscribers for a channel."""
        return len(self._subscribers.get(channel, set()))

    def get_all_channels(self) -> list[str]:
        """Get list of all active channels."""
        return list(self._subscribers.keys())


# Global broadcaster instance
broadcaster = Broadcaster()
