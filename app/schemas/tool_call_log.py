from typing import Optional, List
from pydantic import BaseModel


class ToolCallLogVO(BaseModel):
    id: str
    sessionId: str
    agentId: str
    toolName: str
    toolCallId: str
    arguments: Optional[dict] = None
    status: str
    durationMs: Optional[float] = None
    errorMessage: Optional[str] = None
    resultPreview: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class GetToolCallLogsResponse(BaseModel):
    logs: List[ToolCallLogVO]
    total: int


class ToolCallStatsVO(BaseModel):
    toolName: str
    totalCalls: int
    successCount: int
    failCount: int
    timeoutCount: int
    blockedCount: int
    avgDurationMs: Optional[float] = None
    maxDurationMs: Optional[float] = None
    minDurationMs: Optional[float] = None
    successRate: float


class GetToolCallStatsResponse(BaseModel):
    stats: List[ToolCallStatsVO]
