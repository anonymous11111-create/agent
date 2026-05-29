import time
import logging

from app.agent.state import AgentState
from app.config import settings

logger = logging.getLogger(__name__)


def should_continue(state: AgentState) -> str:
    """Conditional edge: after think, decide whether to execute or end."""
    messages = state.get("messages", [])
    if not messages:
        return "end"

    last_msg = messages[-1]
    tool_calls = getattr(last_msg, "tool_calls", [])

    if state.get("terminated"):
        return "end"

    if state.get("step_count", 0) >= settings.AGENT_MAX_STEPS:
        logger.warning("Max steps reached")
        return "end"

    elapsed = time.monotonic() - state.get("start_time", time.monotonic())
    if elapsed >= settings.AGENT_TIMEOUT_SECONDS:
        logger.warning("Agent timeout (%ds)", elapsed)
        return "end"

    if tool_calls:
        return "execute"

    return "end"
