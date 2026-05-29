import json
import logging

from langchain_core.tools import tool
from langgraph.config import get_config

from app.teams.manager import TEAM, REQUEST_STORE, BUS
from app.teams.bus import VALID_MSG_TYPES

logger = logging.getLogger(__name__)


@tool
async def send_message(to: str, content: str, msg_type: str = "message") -> str:
    """Send a message to a teammate's inbox.

    msg_type options: message, broadcast, shutdown_request, shutdown_response,
    plan_approval, plan_approval_response.
    """
    if msg_type not in VALID_MSG_TYPES:
        return f"Error: Invalid type '{msg_type}'. Valid: {VALID_MSG_TYPES}"
    try:
        config = get_config()
        sender = config["configurable"].get("agent_id", "agent")
        result = BUS.send(sender, to, content, msg_type)
        logger.info("send_message: %s", result)
        return result
    except Exception as e:
        logger.error("send_message failed: %s", e)
        return f"Error: {e}"


@tool
async def read_inbox() -> str:
    """Read and drain the agent's inbox."""
    try:
        config = get_config()
        name = config["configurable"].get("agent_id", "agent")
        messages = BUS.read_inbox(name)
        logger.info("read_inbox: %d messages", len(messages))
        return json.dumps(messages, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("read_inbox failed: %s", e)
        return f"Error: {e}"


@tool
async def broadcast(content: str) -> str:
    """Send a message to all teammates."""
    try:
        config = get_config()
        sender = config["configurable"].get("agent_id", "agent")
        result = BUS.broadcast(sender, content, TEAM.member_names())
        logger.info("broadcast: %s", result)
        return result
    except Exception as e:
        logger.error("broadcast failed: %s", e)
        return f"Error: {e}"


@tool
async def spawn_teammate(name: str, role: str, prompt: str) -> str:
    """Register a persistent teammate with name, role, and initial prompt.

    The teammate can receive messages via send_message and read its inbox.
    """
    try:
        result = TEAM.spawn(name, role, prompt)
        logger.info("spawn_teammate: %s", result)
        return result
    except Exception as e:
        logger.error("spawn_teammate failed: %s", e)
        return f"Error: {e}"


@tool
async def list_teammates() -> str:
    """List all teammates with name, role, and status."""
    try:
        result = TEAM.list_all()
        logger.info("list_teammates: %s", result)
        return result
    except Exception as e:
        logger.error("list_teammates failed: %s", e)
        return f"Error: {e}"


@tool
async def shutdown_request(teammate: str) -> str:
    """Request a teammate to shut down gracefully.

    Returns a request_id for tracking the shutdown protocol.
    """
    try:
        import uuid
        import time

        req_id = str(uuid.uuid4())[:8]
        REQUEST_STORE.create({
            "request_id": req_id,
            "kind": "shutdown",
            "from": "lead",
            "to": teammate,
            "status": "pending",
            "created_at": time.time(),
            "updated_at": time.time(),
        })
        BUS.send("lead", teammate, "Please shut down gracefully.",
                 "shutdown_request", {"request_id": req_id})
        logger.info("shutdown_request sent to %s: %s", teammate, req_id)
        return f"Shutdown request {req_id} sent to '{teammate}' (status: pending)"
    except Exception as e:
        logger.error("shutdown_request failed: %s", e)
        return f"Error: {e}"


@tool
async def plan_approval(request_id: str, approve: bool, feedback: str = "") -> str:
    """Approve or reject a teammate's plan.

    Provide the request_id from the plan_approval message, plus approve flag
    and optional feedback.
    """
    try:
        req = REQUEST_STORE.get(request_id)
        if not req:
            return f"Error: Unknown plan request_id '{request_id}'"
        REQUEST_STORE.update(
            request_id,
            status="approved" if approve else "rejected",
            reviewed_by="lead",
            resolved_at=__import__("time").time(),
            feedback=feedback,
        )
        BUS.send(
            "lead", req["from"], feedback, "plan_approval_response",
            {"request_id": request_id, "approve": approve, "feedback": feedback},
        )
        logger.info("plan_approval %s: %s", request_id, "approved" if approve else "rejected")
        return f"Plan {'approved' if approve else 'rejected'} for '{req['from']}'"
    except Exception as e:
        logger.error("plan_approval failed: %s", e)
        return f"Error: {e}"
