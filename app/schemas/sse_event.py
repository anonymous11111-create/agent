from typing import Optional, Any, List
from pydantic import BaseModel


class ToolCallInfo(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    arguments: Optional[str] = None


class ToolResponseInfo(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    response: Optional[str] = None


class SsePayloadMessage(BaseModel):
    id: str
    sessionId: str
    role: str
    content: Optional[str] = None
    metadata: Optional[dict] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class SseTaskUpdate(BaseModel):
    action: str        # "created" | "updated" | "deleted"
    task: Optional[Any] = None
    taskId: Optional[int] = None


class SsePayload(BaseModel):
    message: Optional[SsePayloadMessage] = None
    statusText: Optional[str] = None
    taskUpdate: Optional[SseTaskUpdate] = None


class SseMetadata(BaseModel):
    chatMessageId: Optional[str] = None


class SseMessage(BaseModel):
    type: str  # "AI_GENERATED_CONTENT"
    payload: Optional[SsePayload] = None
    metadata: Optional[SseMetadata] = None
