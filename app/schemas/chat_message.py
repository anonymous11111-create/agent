from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel


class CreateChatMessageRequest(BaseModel):
    agentId: str
    sessionId: str
    content: str
    role: Optional[str] = "user"


class UpdateChatMessageRequest(BaseModel):
    content: Optional[str] = None


class ChatMessageVO(BaseModel):
    id: str
    sessionId: str
    role: str
    content: Optional[str] = None
    metadata: Optional[dict] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class CreateChatMessageResponse(BaseModel):
    chatMessageId: str


class GetChatMessagesResponse(BaseModel):
    chatMessages: List[ChatMessageVO]
