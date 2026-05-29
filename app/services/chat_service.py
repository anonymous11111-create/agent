import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
    BaseMessage,
)

from app.models.agent import Agent
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.schemas.chat_session import (
    CreateChatSessionRequest,
    ChatSessionVO,
    UpdateChatSessionRequest,
)
from app.schemas.chat_message import (
    CreateChatMessageRequest,
    ChatMessageVO,
)
from app.config import settings

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- Agent helpers ----

    async def get_agent_entity(self, agent_id: str) -> Agent:
        result = await self.db.execute(
            select(Agent).where(Agent.id == uuid.UUID(agent_id))
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")
        return agent

    async def get_agent_model(self, agent_id: str) -> str:
        agent = await self.get_agent_entity(agent_id)
        return agent.model or "deepseek-chat"

    # ---- Session CRUD ----

    async def list_sessions(self) -> list[ChatSessionVO]:
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.type == "NORMAL")
        )
        sessions = result.scalars().all()
        return [self._session_to_vo(s) for s in sessions]

    async def get_session(self, session_id: str) -> Optional[ChatSessionVO]:
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.id == uuid.UUID(session_id))
        )
        session = result.scalar_one_or_none()
        if session:
            return self._session_to_vo(session)
        return None

    async def list_sessions_by_agent(self, agent_id: str) -> list[ChatSessionVO]:
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.agent_id == uuid.UUID(agent_id))
        )
        return [self._session_to_vo(s) for s in result.scalars().all()]

    async def create_session(
        self,
        agent_id: str,
        title: Optional[str] = None,
        session_type: str = "NORMAL",
    ) -> ChatSession:
        session = ChatSession(
            agent_id=uuid.UUID(agent_id),
            title=title,
            type=session_type,
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def delete_session(self, session_id: str):
        await self.db.execute(
            delete(ChatSession).where(ChatSession.id == uuid.UUID(session_id))
        )
        await self.db.flush()

    async def update_session(self, session_id: str, request: UpdateChatSessionRequest):
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.id == uuid.UUID(session_id))
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        if request.title is not None:
            session.title = request.title
        session.updated_at = datetime.now()
        await self.db.flush()

    # ---- Message CRUD ----

    async def list_messages(self, session_id: str) -> list[ChatMessageVO]:
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == uuid.UUID(session_id))
            .order_by(ChatMessage.created_at)
        )
        return [self._message_to_vo(m) for m in result.scalars().all()]

    async def create_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=uuid.UUID(session_id),
            role=role,
            content=content,
            metadata_=metadata,
        )
        self.db.add(msg)
        await self.db.flush()
        return msg

    async def delete_message(self, message_id: str):
        await self.db.execute(
            delete(ChatMessage).where(ChatMessage.id == uuid.UUID(message_id))
        )
        await self.db.flush()

    # ---- Memory loading ----

    async def load_memory(self, session_id: str, message_length: int = 20) -> list[BaseMessage]:
        """Load recent messages from DB and convert to LangChain message types.

        Validates tool call sequences: if an AIMessage has tool_calls but
        corresponding ToolMessages are missing (e.g., due to a crash), the
        tool_calls are stripped to avoid LLM API errors.
        """
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == uuid.UUID(session_id))
            .order_by(ChatMessage.created_at.desc())
            .limit(message_length)
        )
        db_messages = list(reversed(result.scalars().all()))

        lc_messages: list[BaseMessage] = []
        pending_tool_call_ids: set[str] = set()

        for msg in db_messages:
            meta = msg.metadata_ if msg.metadata_ else {}
            if msg.role == "system":
                if msg.content:
                    lc_messages.append(SystemMessage(content=msg.content))
            elif msg.role == "user":
                if msg.content:
                    lc_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                tool_calls = meta.get("toolCalls") or []
                # Track pending tool calls that need responses
                for tc in tool_calls:
                    tc_id = tc.get("id", "")
                    if tc_id:
                        pending_tool_call_ids.add(tc_id)
                lc_messages.append(
                    AIMessage(
                        content=msg.content or "",
                        tool_calls=tool_calls,
                    )
                )
            elif msg.role == "tool":
                tool_response = meta.get("toolResponse", {})
                tc_id = tool_response.get("id", "")
                # Mark this tool call as resolved
                pending_tool_call_ids.discard(tc_id)
                lc_messages.append(
                    ToolMessage(
                        content=msg.content or "",
                        tool_call_id=tc_id,
                        name=tool_response.get("name", ""),
                    )
                )

        # If there are pending tool calls without responses, strip them from
        # the corresponding AIMessages to avoid LLM API errors.
        if pending_tool_call_ids:
            lc_messages = _strip_pending_tool_calls(lc_messages, pending_tool_call_ids)

        # Remove orphaned ToolMessages: ToolMessages whose tool_call_id
        # doesn't match any AIMessage's tool_calls in the loaded window.
        # This happens when the AIMessage is outside the message_length window.
        lc_messages = _remove_orphaned_tool_messages(lc_messages)

        return lc_messages

    # ---- Helpers ----

    def _session_to_vo(self, session: ChatSession) -> ChatSessionVO:
        meta = session.metadata_
        return ChatSessionVO(
            id=str(session.id),
            agentId=str(session.agent_id),
            title=session.title,
            type=session.type,
            metadata=meta,
            createdAt=session.created_at,
            updatedAt=session.updated_at,
        )

    def _message_to_vo(self, msg: ChatMessage) -> ChatMessageVO:
        meta = msg.metadata_
        return ChatMessageVO(
            id=str(msg.id),
            sessionId=str(msg.session_id),
            role=msg.role,
            content=msg.content,
            metadata=meta,
            createdAt=msg.created_at,
            updatedAt=msg.updated_at,
        )


def _strip_pending_tool_calls(messages, pending_ids):
    cleaned = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            resolved = [tc for tc in msg.tool_calls if tc.get("id", "") not in pending_ids]
            if resolved:
                cleaned.append(AIMessage(content=msg.content or "", tool_calls=resolved))
            else:
                cleaned.append(AIMessage(content=msg.content or "", tool_calls=[]))
        else:
            cleaned.append(msg)
    return cleaned


def _remove_orphaned_tool_messages(messages):
    known_tool_call_ids = set()
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tc_id = tc.get("id", "")
                if tc_id:
                    known_tool_call_ids.add(tc_id)

    if not known_tool_call_ids:
        return [m for m in messages if not isinstance(m, ToolMessage)]

    cleaned = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            if msg.tool_call_id in known_tool_call_ids:
                cleaned.append(msg)
        else:
            cleaned.append(msg)
    return cleaned
