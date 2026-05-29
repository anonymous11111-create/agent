"""Confirmation service: manage pending user confirmations for sensitive operations."""
import asyncio
import uuid
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PendingConfirmation:
    confirmation_id: str
    session_id: str
    tool_name: str
    tool_input: dict
    event: asyncio.Event = field(default_factory=asyncio.Event)
    approved: Optional[bool] = None


class ConfirmationService:
    """Track pending confirmations and allow frontend to respond."""

    def __init__(self):
        self._pending: dict[str, PendingConfirmation] = {}

    def create(
        self, session_id: str, tool_name: str, tool_input: dict
    ) -> PendingConfirmation:
        conf_id = str(uuid.uuid4())[:8]
        pc = PendingConfirmation(
            confirmation_id=conf_id,
            session_id=session_id,
            tool_name=tool_name,
            tool_input=tool_input,
        )
        self._pending[conf_id] = pc
        return pc

    def respond(self, confirmation_id: str, approved: bool) -> bool:
        pc = self._pending.get(confirmation_id)
        if not pc:
            return False
        pc.approved = approved
        pc.event.set()
        return True

    async def wait(
        self, pc: PendingConfirmation, timeout: float = 120.0
    ) -> bool:
        """Wait for user response. Returns True if approved."""
        try:
            await asyncio.wait_for(pc.event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("Confirmation %s timed out", pc.confirmation_id)
            pc.approved = False
        finally:
            self._pending.pop(pc.confirmation_id, None)
        return pc.approved is True


confirmation_service = ConfirmationService()
