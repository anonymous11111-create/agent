from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class CreateChatSessionRequest(BaseModel):
    agentId: str
    title: Optional[str] = None
    type: Optional[str] = "NORMAL"


class UpdateChatSessionRequest(BaseModel):
    title: Optional[str] = None


class ChatSessionVO(BaseModel):
    id: str
    agentId: str
    title: Optional[str] = None
    type: Optional[str] = "NORMAL"
    metadata: Optional[dict] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class CreateChatSessionResponse(BaseModel):
    chatSessionId: str


class GetChatSessionResponse(BaseModel):
    chatSession: Optional[ChatSessionVO] = None


class GetChatSessionsResponse(BaseModel):
    chatSessions: List[ChatSessionVO]
