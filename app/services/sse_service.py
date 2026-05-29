import asyncio
import json
import logging
from typing import Optional

from app.schemas.sse_event import SseMessage

logger = logging.getLogger(__name__)


class SseService:
    """Manages SSE connections per session using asyncio.Queue."""

    def __init__(self):
        self._clients: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        if session_id not in self._clients:
            self._clients[session_id] = []
        self._clients[session_id].append(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue):
        if session_id in self._clients:
            try:
                self._clients[session_id].remove(queue)
            except ValueError:
                pass
            if not self._clients[session_id]:
                del self._clients[session_id]

    def send(self, session_id: str, message: SseMessage):
        queues = self._clients.get(session_id, [])
        if not queues:
            logger.warning("No SSE connection for session=%s, message dropped", session_id)
            return
        data = message.model_dump_json()
        dead_queues = []
        for q in queues:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                logger.warning("SSE queue full for session=%s", session_id)
                dead_queues.append(q)
        for q in dead_queues:
            self.unsubscribe(session_id, q)


sse_service = SseService()
