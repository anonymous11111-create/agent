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


class SseToolCallUpdate(BaseModel):
    toolCallLogId: Optional[str] = None
    toolName: Optional[str] = None
    toolCallId: Optional[str] = None
    status: Optional[str] = None  # running/success/fail/timeout/blocked/rejected
    durationMs: Optional[float] = None
    arguments: Optional[dict] = None
    errorMessage: Optional[str] = None


class SseRagQueryUpdate(BaseModel):
    logId: Optional[str] = None
    query: Optional[str] = None
    kbName: Optional[str] = None
    chunks: Optional[list] = None  # [{score, content_preview, doc_filename}]
    chunkCount: Optional[int] = None
    vectorCount: Optional[int] = None
    keywordCount: Optional[int] = None
    totalMs: Optional[float] = None
    scores: Optional[list] = None  # top scores


class SsePayload(BaseModel):
    message: Optional[SsePayloadMessage] = None
    statusText: Optional[str] = None
    taskUpdate: Optional[SseTaskUpdate] = None
    toolCallUpdate: Optional[SseToolCallUpdate] = None
    ragQueryUpdate: Optional[SseRagQueryUpdate] = None
    confirmationId: Optional[str] = None
    toolName: Optional[str] = None
    toolInput: Optional[dict] = None


class SseMetadata(BaseModel):
    chatMessageId: Optional[str] = None


class SseMessage(BaseModel):
    type: str  # "AI_GENERATED_CONTENT"
    payload: Optional[SsePayload] = None
    metadata: Optional[SseMetadata] = None
