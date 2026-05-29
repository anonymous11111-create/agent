import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.sse_service import sse_service

router = APIRouter(tags=["sse"])


@router.get("/sse/connect/{session_id}")
async def sse_connect(session_id: str):
    """SSE endpoint: stream agent events to the frontend."""
    queue = sse_service.subscribe(session_id)

    async def event_generator():
        try:
            # Send init event
            yield f"event: init\ndata: connected\n\n"
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: message\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive ping
                    yield f"event: ping\ndata: keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            sse_service.unsubscribe(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
