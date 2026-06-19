import asyncio
from typing import Dict, List, Any

class EventBus:
    """A simple in-memory pub/sub event bus for streaming events to SSE."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, topic: str) -> asyncio.Queue:
        """Subscribe to a topic and get an async queue."""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        queue = asyncio.Queue()
        self._subscribers[topic].append(queue)
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue):
        """Unsubscribe a specific queue from a topic."""
        if topic in self._subscribers and queue in self._subscribers[topic]:
            self._subscribers[topic].remove(queue)
            if not self._subscribers[topic]:
                del self._subscribers[topic]

    async def publish(self, topic: str, event: Any):
        """Publish an event to all subscribers of a topic."""
        if topic in self._subscribers:
            for queue in self._subscribers[topic]:
                await queue.put(event)

event_bus = EventBus()
