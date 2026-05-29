from typing import Optional, List
from pydantic import BaseModel


class RagQueryLogVO(BaseModel):
    id: str
    sessionId: str
    agentId: str
    knowledgeBaseId: str
    query: str
    kbName: Optional[str] = None
    chunkCount: int = 0
    vectorCount: int = 0
    keywordCount: int = 0
    topScores: Optional[list] = None
    embedMs: Optional[float] = None
    retrievalMs: Optional[float] = None
    fusionMs: Optional[float] = None
    totalMs: Optional[float] = None
    feedback: Optional[str] = None
    createdAt: Optional[str] = None


class FeedbackRequest(BaseModel):
    feedback: str  # "positive" or "negative"


class RagStatsVO(BaseModel):
    totalQueries: int
    avgChunkCount: float
    avgTotalMs: Optional[float] = None
    positiveFeedback: int
    negativeFeedback: int


class GetRagQueryLogsResponse(BaseModel):
    logs: List[RagQueryLogVO]
    total: int
